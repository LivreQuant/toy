// src/services/sse/sse-client.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { config } from '../../config';

export interface SSEOptions {
  reconnectMaxAttempts?: number;
  circuitBreakerThreshold?: number;
  circuitBreakerResetTimeMs?: number;
}

export class SSEClient extends EventEmitter {
  private baseUrl: string;
  private tokenManager: TokenManager;
  private eventSource: EventSource | null = null;
  private sessionId: string | null = null;
  private reconnectTimer: number | null = null;
  private reconnectAttempt: number = 0;
  private maxReconnectAttempts: number;
  private backoffStrategy: BackoffStrategy;
  private isConnecting: boolean = false;
  
  // Circuit breaker properties
  private consecutiveFailures: number = 0;
  private circuitBreakerThreshold: number;
  private circuitBreakerState: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private circuitBreakerResetTime: number;
  private circuitBreakerTrippedAt: number = 0;
  
  constructor(tokenManager: TokenManager, options: SSEOptions = {}) {
    super();
    this.baseUrl = config.sseBaseUrl;
    this.tokenManager = tokenManager;
    this.maxReconnectAttempts = options.reconnectMaxAttempts || 15;
    this.backoffStrategy = new BackoffStrategy(1000, 30000);
    
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
      
      // Build URL with all parameters
      let url = `${this.baseUrl}?sessionId=${sessionId}&token=${token}`;
      
      // Add any additional parameters
      Object.entries(params).forEach(([key, value]) => {
        url += `&${key}=${encodeURIComponent(value)}`;
      });
      
      // Close existing EventSource if any
      this.close();
      
      // Create EventSource
      this.eventSource = new EventSource(url);
      
      return new Promise<boolean>((resolve) => {
        if (!this.eventSource) {
          this.isConnecting = false;
          this.handleConnectionFailure();
          this.emit('connection_failed', { error: 'Failed to create EventSource' });
          resolve(false);
          return;
        }
        
        // Set up event handlers
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
          
          this.emit('connected', { connected: true });
          resolve(true);
        };
        
        this.eventSource.onerror = (error) => {
          console.error('SSE connection error:', error);
          
          if (this.eventSource?.readyState === EventSource.CLOSED) {
            this.handleDisconnect();
          }
          
          if (this.isConnecting) {
            this.isConnecting = false;
            this.handleConnectionFailure();
            this.emit('connection_failed', { error: 'SSE connection error' });
            resolve(false);
          }
        };
        
        // Listen for message event
        this.eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.emit('message', data);
          } catch (error) {
            console.error('Error parsing SSE message:', error);
          }
        };
        
        // Set up timeout for initial connection
        const connectionTimeout = window.setTimeout(() => {
          if (this.isConnecting) {
            this.isConnecting = false;
            this.handleConnectionFailure();
            this.close();
            this.emit('connection_failed', { error: 'SSE connection timeout' });
            resolve(false);
          }
        }, 10000); // 10 second timeout
        
        // Clear timeout on successful connection
        this.once('connected', () => {
          clearTimeout(connectionTimeout);
        });
        
        // Set up custom event listeners
        const eventTypes = ['market-data', 'order-update', 'portfolio-update', 'error'];
        eventTypes.forEach(eventType => {
          this.eventSource?.addEventListener(eventType, (event: MessageEvent) => {
            try {
              const data = JSON.parse(event.data);
              this.emit(eventType, data);
            } catch (error) {
              console.error(`Error parsing SSE ${eventType} event:`, error);
            }
          });
        });
      });
    } catch (error) {
      console.error('SSE connection error:', error);
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
  
  private handleDisconnect(): void {
    // Increment failure counter for disconnects
    this.handleConnectionFailure();
    
    this.emit('disconnected', { reason: 'connection_lost' });
    
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
  
  public close(): void {
    this.stopReconnectTimer();
    
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
  
  private stopReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
  
  public resetCircuitBreaker(): void {
    this.circuitBreakerState = 'CLOSED';
    this.consecutiveFailures = 0;
    this.emit('circuit_reset', { message: 'Circuit breaker manually reset' });
  }
}