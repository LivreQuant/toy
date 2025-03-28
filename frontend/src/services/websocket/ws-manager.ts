// src/services/websocket/ws-manager.ts
import { TokenManager } from '../auth/token-manager';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { EventEmitter } from '../../utils/event-emitter';
import { config } from '../../config';

export interface WebSocketOptions {
  heartbeatInterval?: number;
  reconnectMaxAttempts?: number;
  heartbeatTimeoutMs?: number;
  circuitBreakerThreshold?: number;
  circuitBreakerResetTimeMs?: number;
}

export class WebSocketManager extends EventEmitter {
  private ws: WebSocket | null = null;
  private url: string;
  private isConnecting: boolean = false;
  private backoffStrategy: BackoffStrategy;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private heartbeatTimeout: number | null = null;
  private lastHeartbeatResponse: number = 0;
  private sessionId: string | null = null;
  private tokenManager: TokenManager;
  private reconnectAttempt: number = 0;
  private maxReconnectAttempts: number;
  private heartbeatInterval: number;
  private heartbeatTimeoutMs: number;
  
  // Circuit breaker properties
  private consecutiveFailures: number = 0;
  private circuitBreakerThreshold: number;
  private circuitBreakerState: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private circuitBreakerResetTime: number;
  private circuitBreakerTrippedAt: number = 0;
  
  constructor(tokenManager: TokenManager, options: WebSocketOptions = {}) {
    super();
    this.url = config.wsBaseUrl;
    this.tokenManager = tokenManager;
    this.backoffStrategy = new BackoffStrategy(1000, 30000);
    this.maxReconnectAttempts = options.reconnectMaxAttempts || 15;
    this.heartbeatInterval = options.heartbeatInterval || 15000; // 15 seconds
    this.heartbeatTimeoutMs = options.heartbeatTimeoutMs || 5000; // 5 seconds
    
    // Circuit breaker configuration
    this.circuitBreakerThreshold = options.circuitBreakerThreshold || 5;
    this.circuitBreakerResetTime = options.circuitBreakerResetTimeMs || 60000; // 1 minute
  }
  
  public async connect(sessionId: string): Promise<boolean> {
    // First check if token is available
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      this.emit('error', { error: 'No authentication token available' });
      return false;
    }

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return true;
    }
    
    if (this.isConnecting) {
      return new Promise<boolean>(resolve => {
        this.once('connected', () => resolve(true));
        this.once('connection_failed', () => resolve(false));
      });
    }
    
    // Check circuit breaker status
    if (this.circuitBreakerState === 'OPEN') {
      const currentTime = Date.now();
      if (currentTime - this.circuitBreakerTrippedAt < this.circuitBreakerResetTime) {
        // Circuit is open, fast fail the connection attempt
        this.emit('circuit_open', { 
          message: 'Connection attempts temporarily suspended due to repeated failures',
          resetTimeMs: this.circuitBreakerResetTime - (currentTime - this.circuitBreakerTrippedAt)
        });
        return false;
      } else {
        // Allow one attempt to try to reconnect (half-open state)
        this.circuitBreakerState = 'HALF_OPEN';
        this.emit('circuit_half_open', { 
          message: 'Trying one connection attempt after circuit breaker timeout'
        });
      }
    }
    
    this.isConnecting = true;
    this.sessionId = sessionId;
    
    try {      
      const token = await this.tokenManager.getAccessToken();
      if (!token) {
        this.isConnecting = false;
        this.handleConnectionFailure();
        this.emit('connection_failed', { error: 'No valid token available' });
        return false;
      }
      
      // Create WebSocket connection with token and session ID
      const wsUrl = `${this.url}?token=${token}&sessionId=${sessionId}`;
      this.ws = new WebSocket(wsUrl);
      
      return new Promise<boolean>((resolve) => {
        if (!this.ws) {
          this.isConnecting = false;
          this.handleConnectionFailure();
          this.emit('connection_failed', { error: 'Failed to create WebSocket' });
          resolve(false);
          return;
        }
        
        // Handle WebSocket events
        this.ws.onopen = () => {
          this.isConnecting = false;
          this.reconnectAttempt = 0;
          this.backoffStrategy.reset();
          this.lastHeartbeatResponse = Date.now();
          
          // Reset circuit breaker on successful connection
          this.consecutiveFailures = 0;
          if (this.circuitBreakerState === 'HALF_OPEN') {
            this.circuitBreakerState = 'CLOSED';
            this.emit('circuit_closed', { message: 'Circuit breaker reset after successful connection' });
          }
          
          this.emit('connected', { connected: true });
          this.startHeartbeat();
          resolve(true);
        };
        
        this.ws.onclose = (event) => {
          this.handleDisconnect(event);
          if (this.isConnecting) {
            this.isConnecting = false;
            this.handleConnectionFailure();
            this.emit('connection_failed', { 
              code: event.code, 
              reason: event.reason || 'Connection closed during connect' 
            });
            resolve(false);
          }
        };
        
        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.emit('error', { error });
          if (this.isConnecting) {
            this.isConnecting = false;
            this.handleConnectionFailure();
            this.emit('connection_failed', { error: 'WebSocket connection error' });
            resolve(false);
          }
        };

        this.ws.onmessage = (event) => {
            this.handleMessage(event);
          };
        });
      } catch (error) {
        console.error('WebSocket connection error:', error);
        this.isConnecting = false;
        this.handleConnectionFailure();
        this.emit('connection_failed', { error });
        return false;
      }
    }
    
    private handleConnectionFailure() {
      // Increment failure counter
      this.consecutiveFailures++;
      
      // Check if we should trip the circuit breaker
      if (this.circuitBreakerState !== 'OPEN' && this.consecutiveFailures >= this.circuitBreakerThreshold) {
        this.circuitBreakerState = 'OPEN';
        this.circuitBreakerTrippedAt = Date.now();
        this.emit('circuit_trip', { 
          message: 'Circuit breaker tripped due to consecutive connection failures',
          failureCount: this.consecutiveFailures,
          resetTimeMs: this.circuitBreakerResetTime
        });
      }
    }
    
    public disconnect(): void {
      this.stopHeartbeat();
      this.stopReconnectTimer();
      
      if (this.ws) {
        // Use code 1000 for normal closure
        this.ws.close(1000, 'Client disconnected');
        this.ws = null;
      }
      
      this.emit('disconnected', { reason: 'user_disconnect' });
    }
    
    public send(data: any): boolean {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        return false;
      }
      
      try {
        this.ws.send(typeof data === 'string' ? data : JSON.stringify(data));
        return true;
      } catch (error) {
        console.error('Error sending WebSocket message:', error);
        return false;
      }
    }
    
    private handleMessage(event: MessageEvent): void {
      try {
        // Reset heartbeat timeout on any message
        this.lastHeartbeatResponse = Date.now();
        
        if (this.heartbeatTimeout) {
          clearTimeout(this.heartbeatTimeout);
          this.heartbeatTimeout = null;
        }
        
        // Parse message
        const message = JSON.parse(event.data);
        
        // Handle special message types
        if (message.type === 'heartbeat') {
          this.emit('heartbeat', { timestamp: Date.now() });
          return;
        }
        
        // Emit event based on message type
        if (message.type) {
          this.emit(message.type, message.data || message);
        }
        
        // Always emit the raw message as 'message'
        this.emit('message', message);
      } catch (error) {
        console.error('Error handling WebSocket message:', error);
      }
    }
    
    private handleDisconnect(event: CloseEvent): void {
      this.stopHeartbeat();
      
      const wasClean = event.wasClean;
      const code = event.code;
      const reason = event.reason || 'Unknown reason';
      
      console.log(`WebSocket disconnected: ${reason} (${code})`);
      
      this.emit('disconnected', { 
        wasClean, 
        code, 
        reason 
      });
      
      // Don't reconnect if this was a clean closure
      if (wasClean && code === 1000) {
        return;
      }
      
      // Increment failure counter for non-clean disconnects
      if (!wasClean) {
        this.handleConnectionFailure();
      }
      
      // Attempt to reconnect if circuit breaker allows
      if (this.circuitBreakerState !== 'OPEN') {
        this.attemptReconnect();
      }
    }
    
    private attemptReconnect(): void {
      if (this.reconnectTimer !== null) {
        return; // Already trying to reconnect
      }
      
      if (this.reconnectAttempt >= this.maxReconnectAttempts) {
        this.emit('max_reconnect_attempts', { attempts: this.reconnectAttempt });
        return;
      }
      
      this.reconnectAttempt++;
      
      const delay = this.backoffStrategy.nextBackoffTime();
      
      this.emit('reconnecting', { 
        attempt: this.reconnectAttempt, 
        maxAttempts: this.maxReconnectAttempts,
        delay
      });
      
      this.reconnectTimer = window.setTimeout(async () => {
        this.reconnectTimer = null;
        
        if (this.sessionId) {
          const connected = await this.connect(this.sessionId);
          
          if (!connected && this.circuitBreakerState !== 'OPEN') {
            // If connection failed, try again
            this.attemptReconnect();
          }
        }
      }, delay);
    }
    
    private startHeartbeat(): void {
      this.stopHeartbeat();
      
      this.heartbeatTimer = window.setInterval(() => {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
          this.stopHeartbeat();
          return;
        }
        
        // Send heartbeat
        this.send({ type: 'heartbeat', timestamp: Date.now() });
        
        // Set timeout for heartbeat response
        this.heartbeatTimeout = window.setTimeout(() => {
          console.warn('Heartbeat timeout - no response received');
          
          // Check how long since last heartbeat response
          const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeatResponse;
          
          if (timeSinceLastHeartbeat > this.heartbeatTimeoutMs * 2) {
            console.error('Connection seems dead, forcing reconnect');
            
            // Force reconnect
            if (this.ws) {
              this.ws.close(4000, 'Heartbeat timeout');
              this.ws = null;
            }
            
            this.attemptReconnect();
          }
        }, this.heartbeatTimeoutMs);
      }, this.heartbeatInterval);
    }
    
    private stopHeartbeat(): void {
      if (this.heartbeatTimer !== null) {
        clearInterval(this.heartbeatTimer);
        this.heartbeatTimer = null;
      }
      
      if (this.heartbeatTimeout !== null) {
        clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = null;
      }
    }
    
    private stopReconnectTimer(): void {
      if (this.reconnectTimer !== null) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
    }
    
    public getCircuitBreakerState(): string {
      return this.circuitBreakerState;
    }
    
    public resetCircuitBreaker(): void {
      this.circuitBreakerState = 'CLOSED';
      this.consecutiveFailures = 0;
      this.emit('circuit_reset', { message: 'Circuit breaker manually reset' });
    }
  }