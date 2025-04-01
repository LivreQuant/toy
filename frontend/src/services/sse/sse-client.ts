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
    console.warn('🚨 SSE CLIENT CONSTRUCTOR', {
      baseUrl: config.sseBaseUrl,
      options
    });
    this.baseUrl = config.sseBaseUrl;
    this.tokenManager = tokenManager;
    this.maxReconnectAttempts = options.reconnectMaxAttempts || 15;
    this.backoffStrategy = new BackoffStrategy(1000, 30000);
    
    // Circuit breaker configuration
    this.circuitBreakerThreshold = options.circuitBreakerThreshold || 5;
    this.circuitBreakerResetTime = options.circuitBreakerResetTimeMs || 60000; // 1 minute
  }
  
  public async connect(sessionId: string, params: Record<string, string> = {}): Promise<boolean> {
    console.group('🔍 SSE CONNECTION ATTEMPT');
    console.warn('Connection Params:', { sessionId, params });

    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      console.error('❌ NO ACCESS TOKEN AVAILABLE');
      this.emit('error', { error: 'No authentication token available' });
      console.groupEnd();
      return false;
    }
      
    if (this.eventSource && this.eventSource.readyState === EventSource.OPEN) {
      console.warn('🟢 Already connected');
      console.groupEnd();
      return true;
    }
    
    if (this.isConnecting) {
      console.warn('🔄 Connection in progress');
      console.groupEnd();
      return new Promise<boolean>(resolve => {
        this.once('connected', () => resolve(true));
        this.once('connection_failed', () => resolve(false));
      });
    }
    
    // Check circuit breaker status
    if (this.circuitBreakerState === 'OPEN') {
      const currentTime = Date.now();
      if (currentTime - this.circuitBreakerTrippedAt < this.circuitBreakerResetTime) {
        console.error('🔴 Circuit is OPEN');
        this.emit('circuit_open', { 
          message: 'Connection attempts temporarily suspended',
          resetTimeMs: this.circuitBreakerResetTime - (currentTime - this.circuitBreakerTrippedAt)
        });
        console.groupEnd();
        return false;
      } else {
        this.circuitBreakerState = 'HALF_OPEN';
        console.warn('🟠 Transitioning to HALF_OPEN state');
      }
    }
    
    this.isConnecting = true;
    this.sessionId = sessionId;
    
    try {
      // Construct URL manually with extensive logging
      const urlParams = new URLSearchParams({
        sessionId,
        token,
        ...params
      });
      const fullUrl = `${this.baseUrl}?${urlParams.toString()}`;
      
      console.warn('📡 Full SSE Connection URL:', fullUrl);

      // Create EventSource with maximum debugging
      this.eventSource = new EventSource(fullUrl);
      
      console.warn('🌐 EventSource Created:', {
        readyState: this.eventSource.readyState,
        url: this.eventSource.url
      });

      return new Promise<boolean>((resolve) => {
        this.eventSource!.onopen = () => {
          console.group('🟢 SSE CONNECTION OPENED');
          console.warn('Open Event');
          
          this.isConnecting = false;
          this.reconnectAttempt = 0;
          this.backoffStrategy.reset();
          
          // Reset circuit breaker
          this.consecutiveFailures = 0;
          if (this.circuitBreakerState === 'HALF_OPEN') {
            this.circuitBreakerState = 'CLOSED';
            console.warn('🔓 Circuit breaker reset');
          }
          
          this.emit('connected', { connected: true });
          resolve(true);
          console.groupEnd();
        };
        
        this.eventSource!.onerror = (error) => {
          console.group('🔴 SSE CONNECTION ERROR');
          console.error('Error Event:', error);
          
          if (this.eventSource?.readyState === EventSource.CLOSED) {
            this.handleDisconnect();
          }
          
          if (this.isConnecting) {
            this.isConnecting = false;
            this.handleConnectionFailure();
            this.emit('connection_failed', { error: 'SSE connection error' });
            resolve(false);
          }
          console.groupEnd();
        };
        
        // Verbose message handling
        this.setupVerboseMessageListeners();
      });
    } catch (error) {
      console.group('❌ SSE CONNECTION FAILED');
      console.error('Connection Error:', error);
      this.isConnecting = false;
      this.handleConnectionFailure();
      this.emit('connection_failed', { error });
      console.groupEnd();
      return false;
    }
  }

  private setupVerboseMessageListeners(): void {
    console.warn('🕵️ Setting up VERBOSE Event Listeners');

    // Global message listener
    this.eventSource?.addEventListener('message', (event: MessageEvent) => {
      console.group('🌍 GLOBAL SSE MESSAGE');
      console.warn('Raw Event:', {
        type: event.type,
        data: event.data,
        origin: event.origin
      });
      
      try {
        const parsedData = JSON.parse(event.data);
        console.warn('Parsed Data:', parsedData);
      } catch (parseError) {
        console.error('❌ PARSING ERROR:', parseError);
        console.warn('Unparseable Data:', event.data);
      }
      
      console.groupEnd();
    });

    // Specific market-data event listener
    this.eventSource?.addEventListener('market-data', (event: MessageEvent) => {
      console.group('📊 MARKET DATA EVENT');
      console.warn('Raw Market Data Event:', {
        type: event.type,
        data: event.data
      });
      
      try {
        console.log('Raw market-data event:', event);
        const data = JSON.parse(event.data);
        console.log('Parsed market-data:', data);
        this.emit('message', { type: 'market-data', data });
      } catch (error) {
          console.error(`Error parsing SSE market-data event:`, error, 'Raw event:', event);
      }
      
      console.groupEnd();
    });
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