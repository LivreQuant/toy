// src/services/sse/sse-manager.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { config } from '../../config';
import { ErrorHandler, ErrorSeverity } from '../../utils/error-handler';
import { toastService } from '../../services/notification/toast-service';
import { 
  UnifiedConnectionState, 
  ConnectionServiceType, 
  ConnectionStatus, 
  ServiceState 
} from '../connection/unified-connection-state';

export interface SSEOptions {
  reconnectMaxAttempts?: number;
  circuitBreakerThreshold?: number;
  circuitBreakerResetTimeMs?: number;
  debugMode?: boolean;
}

export class SSEManager extends EventEmitter {
  private baseUrl: string;
  private tokenManager: TokenManager;
  private eventSource: EventSource | null = null;
  private reconnectTimer: number | null = null;
  private reconnectAttempt: number = 0;
  private maxReconnectAttempts: number;
  private backoffStrategy: BackoffStrategy;
  private isConnecting: boolean = false;
  private debugMode: boolean;
  private unifiedState: UnifiedConnectionState;
  
  // Circuit breaker properties
  private consecutiveFailures: number = 0;
  private circuitBreakerThreshold: number;
  private circuitBreakerState: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private circuitBreakerResetTime: number;
  private circuitBreakerTrippedAt: number = 0;
  
  constructor(
    tokenManager: TokenManager, 
    unifiedState: UnifiedConnectionState,
    options: SSEOptions = {}
  ) {
    super();
    this.baseUrl = config.sseBaseUrl;
    this.tokenManager = tokenManager;
    this.unifiedState = unifiedState;
    this.maxReconnectAttempts = options.reconnectMaxAttempts || 15;
    this.backoffStrategy = new BackoffStrategy(1000, 30000);
    this.debugMode = options.debugMode || false;
    
    // Circuit breaker configuration
    this.circuitBreakerThreshold = options.circuitBreakerThreshold || 5;
    this.circuitBreakerResetTime = options.circuitBreakerResetTimeMs || 60000; // 1 minute
    
    if (this.debugMode) {
      console.warn('🚨 SSE MANAGER INITIALIZED', {
        baseUrl: this.baseUrl,
        options
      });
    }
    
    // Subscribe to WebSocket state changes
    this.unifiedState.on('websocket_state_change', this.handleWebSocketStateChange.bind(this));
  }
  
  // Handle WebSocket state changes to coordinate SSE behavior
  private handleWebSocketStateChange({ state }: { service: ConnectionServiceType, state: ServiceState }): void {
    if (state.status === ConnectionStatus.CONNECTED && 
        this.unifiedState.getServiceState(ConnectionServiceType.SSE).status !== ConnectionStatus.CONNECTED) {
      // WebSocket is connected, try to connect SSE if not already connected
      this.connect().catch(err => 
        console.error('Failed to connect SSE after WebSocket connected:', err)
      );
    } else if (state.status === ConnectionStatus.DISCONNECTED) {
      // WebSocket is disconnected, disconnect SSE as well
      this.close();
      this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.DISCONNECTED,
        error: 'WebSocket disconnected'
      });
    }
  }
  
  public async connect(): Promise<boolean> {
    if (this.debugMode) {
      console.group('🔍 SSE CONNECTION ATTEMPT');
    }

    // Check if WebSocket is connected first
    const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    if (wsState.status !== ConnectionStatus.CONNECTED) {
      if (this.debugMode) {
        console.error('❌ WebSocket not connected, cannot connect SSE');
        console.groupEnd();
      }
      this.emit('error', { error: 'Cannot connect SSE when WebSocket is disconnected' });
      return false;
    }

    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      if (this.debugMode) {
        console.error('❌ NO ACCESS TOKEN AVAILABLE');
        console.groupEnd();
      }
      this.emit('error', { error: 'No authentication token available' });
      return false;
    }
      
    if (this.eventSource && this.eventSource.readyState === EventSource.OPEN) {
      if (this.debugMode) {
        console.warn('🟢 Already connected');
        console.groupEnd();
      }
      return true;
    }
    
    if (this.isConnecting) {
      if (this.debugMode) {
        console.warn('🔄 Connection in progress');
        console.groupEnd();
      }
      return new Promise<boolean>(resolve => {
        this.once('connected', () => resolve(true));
        this.once('connection_failed', () => resolve(false));
      });
    }
    
    // Check circuit breaker status
    if (this.circuitBreakerState === 'OPEN') {
      const currentTime = Date.now();
      if (currentTime - this.circuitBreakerTrippedAt < this.circuitBreakerResetTime) {
        if (this.debugMode) {
          console.error('🔴 Circuit is OPEN');
          console.groupEnd();
        }
        this.emit('circuit_open', { 
          message: 'Connection attempts temporarily suspended',
          resetTimeMs: this.circuitBreakerResetTime - (currentTime - this.circuitBreakerTrippedAt)
        });
        return false;
      } else {
        this.circuitBreakerState = 'HALF_OPEN';
        if (this.debugMode) {
          console.warn('🟠 Transitioning to HALF_OPEN state');
        }
      }
    }
    
    this.isConnecting = true;
    
    // Update unified state
    this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
      status: ConnectionStatus.CONNECTING,
      error: null
    });
    
    try {
      // Construct URL with just token
      const fullUrl = `${this.baseUrl}?token=${token}`;
      
      if (this.debugMode) {
        console.warn('📡 Full SSE Connection URL:', fullUrl);
      }

      // Create EventSource
      this.eventSource = new EventSource(fullUrl);
      
      if (this.debugMode) {
        console.warn('🌐 EventSource Created:', {
          readyState: this.eventSource.readyState,
          url: this.eventSource.url
        });
      }

      return new Promise<boolean>((resolve) => {
        this.eventSource!.onopen = () => {
          if (this.debugMode) {
            console.group('🟢 SSE CONNECTION OPENED');
            console.warn('Open Event');
          }
          
          this.isConnecting = false;
          this.reconnectAttempt = 0;
          this.backoffStrategy.reset();
          
          // Reset circuit breaker
          this.consecutiveFailures = 0;
          if (this.circuitBreakerState === 'HALF_OPEN') {
            this.circuitBreakerState = 'CLOSED';
            if (this.debugMode) {
              console.warn('🔓 Circuit breaker reset');
            }
          }
          
          // Update unified state
          this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
            status: ConnectionStatus.CONNECTED,
            lastConnected: Date.now(),
            error: null
          });
          
          this.emit('connected', { connected: true });
          resolve(true);
          
          if (this.debugMode) {
            console.groupEnd();
          }
        };
        
        this.eventSource!.onerror = (error) => {
          if (this.debugMode) {
            console.group('🔴 SSE CONNECTION ERROR');
            console.error('Error Event:', error);
          }
          
          if (this.eventSource?.readyState === EventSource.CLOSED) {
            this.handleDisconnect();
          }
          
          if (this.isConnecting) {
            this.isConnecting = false;
            this.handleConnectionFailure();
            
            // Update unified state
            this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
              status: ConnectionStatus.DISCONNECTED,
              error: 'SSE connection error'
            });
            
            this.emit('connection_failed', { error: 'SSE connection error' });
            resolve(false);
          }
          
          if (this.debugMode) {
            console.groupEnd();
          }
        };
        
        // Set up message listeners
        this.setupMessageListeners();
      });
    } catch (error) {
      if (this.debugMode) {
        console.group('❌ SSE CONNECTION FAILED');
        console.error('Connection Error:', error);
        console.groupEnd();
      }
      
      this.isConnecting = false;
      this.handleConnectionFailure();
      
      // Update unified state
      this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.DISCONNECTED,
        error: error instanceof Error ? error.message : String(error)
      });
      
      this.emit('connection_failed', { error });
      return false;
    }
  }

  private setupMessageListeners(): void {
    if (!this.eventSource) return;
    
    // Global message listener
    this.eventSource.addEventListener('message', (event: MessageEvent) => {
      if (this.debugMode) {
        console.group('🌍 SSE MESSAGE');
        console.warn('Raw Event:', {
          type: event.type,
          data: event.data,
          origin: event.origin
        });
      }
      
      try {
        const parsedData = JSON.parse(event.data);
        
        if (this.debugMode) {
          console.warn('Parsed Data:', parsedData);
        }
        
        // Emit the parsed message
        this.emit('message', { type: 'message', data: parsedData });
      } catch (parseError) {
        if (this.debugMode) {
          console.error('❌ PARSING ERROR:', parseError);
          console.warn('Unparseable Data:', event.data);
        }
        this.emit('error', { 
          error: 'Failed to parse SSE message', 
          originalError: parseError, 
          rawData: event.data 
        });
      }
      
      if (this.debugMode) {
        console.groupEnd();
      }
    });

    // Set up single event listener for exchange data
    this.eventSource.addEventListener('exchange-data', (event: MessageEvent) => {
      if (this.debugMode) {
        console.group('📊 EXCHANGE DATA EVENT');
        console.warn('Raw exchange-data Event:', {
          type: event.type,
          data: event.data
        });
      }
      
      try {
        const data = JSON.parse(event.data);
        
        if (this.debugMode) {
          console.log('Parsed exchange-data:', data);
        }
        
        // Emit the exchange data event
        this.emit('exchange-data', data);
        
        // Also emit as a general message with type
        this.emit('message', { type: 'exchange-data', data });
      } catch (error) {
        if (this.debugMode) {
          console.error('Error parsing SSE exchange-data event:', error, 'Raw event:', event);
        }
        this.emit('error', { 
          error: 'Failed to parse exchange-data event', 
          originalError: error, 
          rawData: event.data 
        });
      }
      
      if (this.debugMode) {
        console.groupEnd();
      }
    });
    
    // Error event listener
    this.eventSource.addEventListener('error-event', (event: MessageEvent) => {
      try {
        const errorData = JSON.parse(event.data);
        this.emit('error', errorData);
      } catch (error) {
        this.emit('error', { 
          error: 'Server reported an error', 
          rawData: event.data 
        });
      }
    });
  }

  private handleConnectionFailure() {
    // Increment failure counter
    this.consecutiveFailures++;
    
    // Update unified state
    this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
      status: ConnectionStatus.DISCONNECTED,
      error: `Connection failure (attempt ${this.consecutiveFailures})`
    });
    
    // Check if we should trip the circuit breaker
    if (this.circuitBreakerState !== 'OPEN' && this.consecutiveFailures >= this.circuitBreakerThreshold) {
      this.circuitBreakerState = 'OPEN';
      this.circuitBreakerTrippedAt = Date.now();
      this.emit('circuit_trip', { 
        message: 'Circuit breaker tripped due to consecutive connection failures',
        failureCount: this.consecutiveFailures,
        resetTimeMs: this.circuitBreakerResetTime
      });
      
      // Use standardized error handler for circuit breaker
      ErrorHandler.handleConnectionError(
        'Multiple connection failures detected. Data stream temporarily disabled.',
        ErrorSeverity.HIGH,
        'Data Stream'
      );
    } else if (this.consecutiveFailures > 1) {
      // Use standardized error handler for general failures
      ErrorHandler.handleConnectionError(
        'Connection to data stream failed.',
        ErrorSeverity.MEDIUM,
        'Data Stream'
      );
    }
  }
  
  private handleDisconnect(): void {
    // Increment failure counter for disconnects
    this.handleConnectionFailure();
    
    this.emit('disconnected', { reason: 'connection_lost' });
    
    // Update unified state
    this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
      status: ConnectionStatus.DISCONNECTED,
      error: 'Connection lost'
    });
    
    // Attempt to reconnect if circuit breaker allows and WebSocket is connected
    if (this.circuitBreakerState !== 'OPEN' && 
        this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status === ConnectionStatus.CONNECTED) {
      this.attemptReconnect();
    }
    
    // Use standardized error handler for disconnect
    ErrorHandler.handleConnectionError(
      'Market data stream connection lost',
      ErrorSeverity.MEDIUM,
      'Data Stream'
    );

    // Emit specific events for UI
    this.emit('connection_lost', {
      reason: 'Market data stream interrupted'
    });
  }
    
  private attemptReconnect(): void {
    if (this.reconnectTimer !== null) {
      return; // Already trying to reconnect
    }
    
    // Check if WebSocket is connected first
    if (this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status !== ConnectionStatus.CONNECTED) {
      if (this.debugMode) {
        console.warn('⚠️ Not attempting SSE reconnect because WebSocket is disconnected');
      }
      return;
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
      
      const connected = await this.connect();
      
      if (!connected && this.circuitBreakerState !== 'OPEN') {
        // If connection failed, try again
        this.attemptReconnect();
      }
    }, delay);

    // Replace direct toast with standardized notification
    ErrorHandler.handleConnectionError(
      `Reconnecting to market data stream (Attempt ${this.reconnectAttempt})...`,
      ErrorSeverity.LOW,
      'Data Stream'
    );
  }
  
  public close(): void {
    this.stopReconnectTimer();
    
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    
    // Update unified state
    this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
      status: ConnectionStatus.DISCONNECTED,
      error: null
    });
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
  
  public getConnectionStatus(): {
    connected: boolean;
    connecting: boolean;
    circuitBreakerState: string;
    reconnectAttempt: number;
    maxReconnectAttempts: number;
  } {
    return {
      connected: !!this.eventSource && this.eventSource.readyState === EventSource.OPEN,
      connecting: this.isConnecting,
      circuitBreakerState: this.circuitBreakerState,
      reconnectAttempt: this.reconnectAttempt,
      maxReconnectAttempts: this.maxReconnectAttempts
    };
  }
  
  public dispose(): void {
    this.close();
    this.removeAllListeners();
  }
}