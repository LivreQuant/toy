// frontend/src/services/sse/sse-client.ts

import { TokenManager } from '../auth/token-manager';
import { BackoffStrategy } from '../websocket/backoff-strategy';

export interface SSEOptions {
  reconnectMaxAttempts?: number;
  initialReconnectDelayMs?: number;
  maxReconnectDelayMs?: number;
  reconnectOnError?: boolean;
  circuitBreakerThreshold?: number;
  circuitBreakerResetTimeMs?: number;
}

export class SSEClient {
  private url: string;
  private tokenManager: TokenManager;
  private eventSource: EventSource | null = null;
  private backoffStrategy: BackoffStrategy;
  private isConnecting: boolean = false;
  private reconnectTimer: number | null = null;
  private sessionId: string | null = null;
  private eventHandlers: Map<string, Set<Function>> = new Map();
  private reconnectAttempt: number = 0;
  private maxReconnectAttempts: number;
  private reconnectOnError: boolean;
  private lastEventId: string | null = null;
  private params: Record<string, string> = {};
  
  // Circuit breaker properties
  private consecutiveFailures: number = 0;
  private circuitBreakerThreshold: number;
  private circuitBreakerState: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private circuitBreakerResetTime: number;
  private circuitBreakerTrippedAt: number = 0;
  
  constructor(url: string, tokenManager: TokenManager, options: SSEOptions = {}) {
    this.url = url;
    this.tokenManager = tokenManager;
    this.backoffStrategy = new BackoffStrategy(
      options.initialReconnectDelayMs || 1000,
      options.maxReconnectDelayMs || 30000
    );
    this.maxReconnectAttempts = options.reconnectMaxAttempts || 10;
    this.reconnectOnError = options.reconnectOnError !== false;
    
    // Circuit breaker configuration
    this.circuitBreakerThreshold = options.circuitBreakerThreshold || 5;
    this.circuitBreakerResetTime = options.circuitBreakerResetTimeMs || 60000; // 1 minute
  }
  
  public async connect(sessionId: string, params: Record<string, string> = {}): Promise<boolean> {
    if (this.eventSource && this.eventSource.readyState === EventSource.OPEN) {
      return true;
    }
    
    if (this.isConnecting) {
      return new Promise<boolean>(resolve => {
        this.once('open', () => resolve(true));
        this.once('error', () => resolve(false));
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
    this.params = { ...params };
    
    try {
      // Close existing connection if any
      this.close();
      
      const token = await this.tokenManager.getAccessToken();
      if (!token) {
        this.isConnecting = false;
        this.handleConnectionFailure();
        return false;
      }
      
      // Add session ID, token and other params to the URL
      let sseUrl = `${this.url}?sessionId=${sessionId}&token=${token}`;
      
      // Add any additional parameters
      Object.entries(params).forEach(([key, value]) => {
        sseUrl += `&${key}=${encodeURIComponent(value)}`;
      });
      
      // Add last event ID if available for resuming stream
      if (this.lastEventId) {
        sseUrl += `&lastEventId=${this.lastEventId}`;
      }
      
      // Create SSE connection
      this.eventSource = new EventSource(sseUrl);
      
      return new Promise<boolean>((resolve) => {
        if (!this.eventSource) {
          this.isConnecting = false;
          this.handleConnectionFailure();
          resolve(false);
          return;
        }
        
        // Handle SSE events
        this.eventSource.onopen = () => {
          this.isConnecting = false;
          this.reconnectAttempt = 0;
          this.backoffStrategy.reset();
          
          // Reset circuit breaker on successful connection
          this.consecutiveFailures = 0;
          if (this.circuitBreakerState === 'HALF_OPEN') {
            this.circuitBreakerState = 'CLOSED';
            this.emit('circuit_closed', { message: 'Circuit breaker reset after successful connection' });
          }
          
          this.emit('open', { connected: true });
          resolve(true);
        };
        
        this.eventSource.onerror = (error) => {
          console.error('SSE error:', error);
          this.emit('error', { error });
          
          if (this.isConnecting) {
            this.isConnecting = false;
            this.handleConnectionFailure();
            resolve(false);
          }
          
          // Handle reconnection on error
          if (this.reconnectOnError && this.circuitBreakerState !== 'OPEN') {
            this.handleDisconnect();
          }
        };
        
        // Add message event listener
        this.eventSource.addEventListener('message', (event: MessageEvent) => {
          this.handleMessage(event);
        });
        
        // Add custom event listeners
        ['market-data', 'order-update', 'portfolio-update', 'connection', 'error'].forEach(eventType => {
          this.eventSource?.addEventListener(eventType, (event: MessageEvent) => {
            this.handleEvent(eventType, event);
          });
        });
      });
    } catch (error) {
      console.error('SSE connection error:', error);
      this.isConnecting = false;
      this.handleConnectionFailure();
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
  
  public close(): void {
    this.stopReconnectTimer();
    
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    
    this.emit('close', { reason: 'user_disconnect' });
  }
  
  public on(event: string, callback: Function): void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set());
    }
    
    this.eventHandlers.get(event)?.add(callback);
  }
  
  public off(event: string, callback: Function): void {
    const callbacks = this.eventHandlers.get(event);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }
  
  public once(event: string, callback: Function): void {
    const onceCallback = (...args: any[]) => {
      this.off(event, onceCallback);
      callback(...args);
    };
    
    this.on(event, onceCallback);
  }
  
  public emit(event: string, data: any): void {
    const callbacks = this.eventHandlers.get(event);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in SSE event handler for ${event}:`, error);
        }
      });
    }
    
    // Also emit to wildcard listeners
    const wildcardCallbacks = this.eventHandlers.get('*');
    if (wildcardCallbacks) {
      wildcardCallbacks.forEach(callback => {
        try {
          callback(event, data);
        } catch (error) {
          console.error(`Error in SSE wildcard event handler for ${event}:`, error);
        }
      });
    }
  }
  
  private handleMessage(event: MessageEvent): void {
    try {
      // Store last event ID for resuming stream if available
      if (event.lastEventId) {
        this.lastEventId = event.lastEventId;
      }
      
      // Parse message data if it's a string
      let data = event.data;
      if (typeof data === 'string') {
        try {
          data = JSON.parse(data);
        } catch {
          // Keep as string if not valid JSON
        }
      }
      
      // Emit the message event
      this.emit('message', data);
    } catch (error) {
      console.error('Error handling SSE message:', error);
    }
  }
  
  private handleEvent(eventType: string, event: MessageEvent): void {
    try {
      // Store last event ID for resuming stream if available
      if (event.lastEventId) {
        this.lastEventId = event.lastEventId;
      }
      
      // Parse event data if it's a string
      let data = event.data;
      if (typeof data === 'string') {
        try {
          data = JSON.parse(data);
        } catch {
          // Keep as string if not valid JSON
        }
      }
      
      // Emit the specific event type
      this.emit(eventType, data);
    } catch (error) {
      console.error(`Error handling SSE event ${eventType}:`, error);
    }
  }
  
  private handleDisconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    
    this.emit('close', { reason: 'error' });
    
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
        const connected = await this.connect(this.sessionId, this.params);
        
        if (!connected && this.circuitBreakerState !== 'OPEN') {
          // If connection failed, try again
          this.attemptReconnect();
        }
      }
    }, delay);
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