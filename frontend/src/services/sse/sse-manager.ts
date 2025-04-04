// src/services/sse/sse-manager.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { config } from '../../config';
import { ErrorHandler, ErrorSeverity } from '../../utils/error-handler';
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus,
  ServiceState
} from '../connection/unified-connection-state';
import { CircuitBreaker, CircuitState } from '../../utils/circuit-breaker'; // Import CircuitBreaker
import { Logger } from '../../utils/logger'; // Import Logger

export interface SSEOptions {
  reconnectMaxAttempts?: number;
  // Circuit breaker options now passed directly to the utility
  failureThreshold?: number;
  resetTimeoutMs?: number;
  // debugMode?: boolean; // Replaced by logger injection
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
  private unifiedState: UnifiedConnectionState;
  private circuitBreaker: CircuitBreaker; // Use CircuitBreaker utility
  private logger: Logger; // Use Logger utility

  constructor(
    tokenManager: TokenManager,
    unifiedState: UnifiedConnectionState,
    logger: Logger, // Inject Logger
    options: SSEOptions = {}
  ) {
    super();
    this.baseUrl = config.sseBaseUrl;
    this.tokenManager = tokenManager;
    this.unifiedState = unifiedState;
    this.logger = logger; // Assign logger
    this.maxReconnectAttempts = options.reconnectMaxAttempts ?? 15;
    this.backoffStrategy = new BackoffStrategy(1000, 30000);

    // Initialize Circuit Breaker
    this.circuitBreaker = new CircuitBreaker(
        'sse-connection',
        options.failureThreshold ?? 5,
        options.resetTimeoutMs ?? 60000 // 1 minute default reset timeout
    );

    // Log circuit breaker state changes
    this.circuitBreaker.onStateChange((name, oldState, newState, info) => {
        this.logger.warn(`Circuit Breaker [${name}] state changed: ${oldState} -> ${newState}`, info);
        if (newState === CircuitState.OPEN) {
             ErrorHandler.handleConnectionError(
                'Multiple SSE connection failures detected. Data stream temporarily disabled.',
                ErrorSeverity.HIGH,
                'Data Stream (SSE)'
             );
             this.emit('circuit_open', {
                message: 'SSE Connection attempts temporarily suspended due to repeated failures.',
                resetTimeoutMs: options.resetTimeoutMs ?? 60000
             });
        } else if (newState === CircuitState.CLOSED) {
             this.emit('circuit_closed', { message: 'SSE Circuit breaker closed. Connections re-enabled.' });
        }
    });


    this.logger.info('SSE Manager Initialized', {
      baseUrl: this.baseUrl,
      options: {
          reconnectMaxAttempts: this.maxReconnectAttempts,
          failureThreshold: options.failureThreshold ?? 5,
          resetTimeoutMs: options.resetTimeoutMs ?? 60000
      }
    });

    // Subscribe to WebSocket state changes
    this.unifiedState.on('websocket_state_change', this.handleWebSocketStateChange.bind(this));
  }

  private handleWebSocketStateChange({ state }: { service: ConnectionServiceType, state: ServiceState }): void {
    this.logger.info(`Handling WebSocket state change in SSEManager: WS Status = ${state.status}`);
    const sseCurrentStatus = this.unifiedState.getServiceState(ConnectionServiceType.SSE).status;

    if (state.status === ConnectionStatus.CONNECTED &&
        sseCurrentStatus !== ConnectionStatus.CONNECTED &&
        sseCurrentStatus !== ConnectionStatus.CONNECTING) {
      this.logger.info('WebSocket connected. Triggering SSE connect attempt.');
      // Reset circuit breaker manually if WS reconnects successfully, allowing SSE to try again sooner
      if(this.circuitBreaker.getState() === CircuitState.OPEN) {
          this.logger.warn('Resetting SSE circuit breaker due to successful WebSocket connection.');
          this.circuitBreaker.reset();
      }
      this.connect().catch(err =>
        this.logger.error('Failed to auto-connect SSE after WebSocket connected', { error: err })
      );
    } else if (state.status === ConnectionStatus.DISCONNECTED) {
       this.logger.warn('WebSocket disconnected. Closing SSE connection.');
      this.close(); // Close SSE connection
       // Explicitly set SSE state to disconnected due to WS disconnect
      this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.DISCONNECTED,
        error: 'WebSocket disconnected'
      });
    }
  }

  public async connect(): Promise<boolean> {
    this.logger.info('SSE connection attempt initiated.');

    // Check if WebSocket is connected first
    const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    if (wsState.status !== ConnectionStatus.CONNECTED) {
      this.logger.error('SSE connect aborted: WebSocket is not connected.', { wsStatus: wsState.status });
      this.emit('error', { error: 'Cannot connect SSE when WebSocket is disconnected' });
      // Don't mark circuit breaker failure if WS is down
      return false;
    }

    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      this.logger.error('SSE connect aborted: No authentication token available.');
      this.emit('error', { error: 'No authentication token available for SSE' });
      // Don't mark circuit breaker failure for auth issues
      return false;
    }

    if (this.eventSource && this.eventSource.readyState === EventSource.OPEN) {
      this.logger.warn('SSE connect skipped: Already connected.');
      return true;
    }

    if (this.isConnecting) {
      this.logger.warn('SSE connect skipped: Connection already in progress.');
      // Optional: Return promise that resolves when current connection attempt finishes
      return new Promise<boolean>(resolve => {
        this.once('connected', () => resolve(true));
        this.once('connection_failed', () => resolve(false)); // Listen for specific failure event
      });
    }

    // *** Use Circuit Breaker ***
    try {
       return await this.circuitBreaker.execute(async () => {
           return await this.establishConnection(token);
       });
    } catch (error: any) {
        // Errors thrown by circuit breaker (OPEN state) or establishConnection
        this.logger.error('SSE connection failed via circuit breaker or internal error.', { error: error.message });
        this.handleConnectionFailure(error instanceof Error ? error.message : String(error));
        // Ensure state is updated
        this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
            status: ConnectionStatus.DISCONNECTED,
            error: `Connection failed: ${error.message}`
        });
        this.emit('connection_failed', { error: error.message });
        return false;
    }
  }

  // Extracted core connection logic to be wrapped by circuit breaker
  private async establishConnection(token: string): Promise<boolean> {
      this.isConnecting = true;
      this.logger.info('Establishing SSE connection...');
      this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.CONNECTING,
        error: null
      });

      try {
        const fullUrl = `${this.baseUrl}?token=${token}`;
        this.logger.info('SSE Connection URL', { url: this.baseUrl }); // Log base URL only for security

        // Close existing EventSource if any before creating a new one
        if (this.eventSource) {
            this.eventSource.close();
            this.removeMessageListeners(); // Clean up old listeners
        }

        this.eventSource = new EventSource(fullUrl);
        this.logger.info('EventSource instance created.');

        return new Promise<boolean>((resolve) => {
          this.eventSource!.onopen = () => {
            this.logger.info('SSE Connection Opened Successfully.');
            this.isConnecting = false;
            this.reconnectAttempt = 0;
            this.backoffStrategy.reset();
            // No need to call circuitBreaker.success() here, handled by execute wrapper

            this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
              status: ConnectionStatus.CONNECTED,
              lastConnected: Date.now(),
              error: null
            });
            this.emit('connected', { connected: true });
            resolve(true);
          };

          this.eventSource!.onerror = (errorEvent) => {
             // This onerror often triggers even for successful reconnects after a network blip.
             // Check readyState to distinguish fatal errors from temporary ones.
            this.logger.error('SSE onerror Event Triggered.', { readyState: this.eventSource?.readyState });

            if (this.eventSource?.readyState === EventSource.CLOSED) {
                 this.logger.warn('SSE onerror: Connection closed. Handling disconnect.');
                 // This is a definite disconnect
                 this.handleDisconnect('onerror_closed'); // Pass reason
                 // Reject the promise only if we were initially connecting
                 if (this.isConnecting) {
                     this.isConnecting = false;
                     this.emit('connection_failed', { error: 'SSE connection error during setup' });
                     resolve(false); // Failed initial connection
                 } else {
                    // If already connected, this handler just notes the error, handleDisconnect takes over
                 }

            } else if (this.eventSource?.readyState === EventSource.CONNECTING) {
                // Browser is attempting reconnect internally, log but don't overreact yet
                this.logger.warn('SSE onerror: Connection in connecting state (likely browser retry).');
            } else {
                 this.logger.error('SSE onerror: Unknown state.', { errorEvent });
                 // Potentially handle as disconnect if needed
            }
          };

          this.setupMessageListeners(); // Setup listeners for the new EventSource
        });
      } catch (error: any) {
        this.logger.error('SSE establishConnection caught error', { error: error.message });
        this.isConnecting = false;
        // Throw error so circuit breaker catches it
        throw error;
      }
  }


  private setupMessageListeners(): void {
    if (!this.eventSource) return;
    this.logger.info('Setting up SSE message listeners.');

    this.eventSource.onmessage = (event: MessageEvent) => { // Generic 'message' event
       this.logger.info('SSE generic message received', { data: event.data });
        try {
            const parsedData = JSON.parse(event.data);
            this.emit('message', { type: 'message', data: parsedData });
        } catch (parseError: any) {
            this.logger.error('Failed to parse generic SSE message', { error: parseError.message, rawData: event.data });
            this.emit('error', { error: 'Failed to parse SSE message', originalError: parseError, rawData: event.data });
        }
    };

    this.eventSource.addEventListener('exchange-data', (event: MessageEvent) => {
       this.logger.info('SSE exchange-data event received'); // Don't log data itself unless necessary
        try {
            const data = JSON.parse(event.data);
            this.emit('exchange-data', data);
            this.emit('message', { type: 'exchange-data', data });
        } catch (error: any) {
             this.logger.error('Failed to parse exchange-data event', { error: error.message, rawData: event.data });
             this.emit('error', { error: 'Failed to parse exchange-data event', originalError: error, rawData: event.data });
        }
    });

    // Example: Listener for a custom 'order-update' event
     this.eventSource.addEventListener('order-update', (event: MessageEvent) => {
       this.logger.info('SSE order-update event received');
        try {
            const data = JSON.parse(event.data);
            this.emit('order-update', data);
            this.emit('message', { type: 'order-update', data });
        } catch (error: any) {
             this.logger.error('Failed to parse order-update event', { error: error.message, rawData: event.data });
             this.emit('error', { error: 'Failed to parse order-update event', originalError: error, rawData: event.data });
        }
    });

    // Listen for a potential 'error-event' from the server itself
    this.eventSource.addEventListener('error-event', (event: MessageEvent) => {
       this.logger.error('SSE server-sent error event received', { data: event.data });
        try {
            const errorData = JSON.parse(event.data);
            this.emit('server_error', errorData); // More specific event name
            this.emit('error', { type: 'server_error', data: errorData });
        } catch (error) {
            this.emit('error', { error: 'Server reported an unparseable error', rawData: event.data });
        }
    });
  }

  // Clean up listeners - Important when recreating EventSource
  private removeMessageListeners(): void {
       if (!this.eventSource) return;
       this.logger.info('Removing SSE message listeners.');
       this.eventSource.onmessage = null;
       this.eventSource.removeEventListener('exchange-data', () => {}); // Pass dummy listener for removal
       this.eventSource.removeEventListener('order-update', () => {});
       this.eventSource.removeEventListener('error-event', () => {});
       // Remove other custom listeners here
  }


  private handleConnectionFailure(errorMessage: string) {
    // Failure is now primarily handled by the Circuit Breaker's execute wrapper throwing an error.
    // This function is mostly for logging and emitting specific events if needed.
    this.logger.warn(`SSE Connection Failure: ${errorMessage}`);
     this.isConnecting = false; // Ensure connecting flag is reset

    // Update unified state (might be redundant if already set in connect error handler)
    this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
      status: ConnectionStatus.DISCONNECTED,
      error: `Connection failure: ${errorMessage}`
    });

    // Emit a specific failure event (useful for UI/logging)
    this.emit('connection_failed', { error: errorMessage });

     // Check if circuit breaker is open and notify via ErrorHandler
     if (this.circuitBreaker.getState() === CircuitState.OPEN) {
         ErrorHandler.handleConnectionError(
            `SSE connection failed and circuit breaker is OPEN. Attempts suspended. Reason: ${errorMessage}`,
            ErrorSeverity.HIGH,
            'Data Stream (SSE)'
         );
     } else {
          ErrorHandler.handleConnectionError(
            `SSE connection failed. Reason: ${errorMessage}`,
            ErrorSeverity.MEDIUM,
            'Data Stream (SSE)'
         );
     }
  }

  private handleDisconnect(reason: string = 'unknown'): void {
    this.logger.warn(`SSE Disconnected. Reason: ${reason}`);
     this.isConnecting = false; // Ensure connecting flag is reset

    // Only attempt reconnect if the disconnect wasn't initiated by closing the WS or manually
    const shouldAttemptReconnect = reason !== 'websocket_disconnected' && reason !== 'manual_close';


    // Update unified state immediately
     const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
     if (sseState.status !== ConnectionStatus.DISCONNECTED) {
         this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
           status: ConnectionStatus.DISCONNECTED,
           error: `Connection lost (${reason})`
         });
          this.emit('disconnected', { reason }); // Emit disconnect event only once
     }


    // Attempt to reconnect if allowed by circuit breaker AND WebSocket is connected
    if (shouldAttemptReconnect && this.circuitBreaker.getState() !== CircuitState.OPEN &&
        this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status === ConnectionStatus.CONNECTED) {
      this.logger.info('Attempting SSE reconnect after disconnect.');
      this.attemptReconnect();
    } else {
       this.logger.warn('Not attempting SSE reconnect.', {
           shouldAttemptReconnect,
           circuitState: this.circuitBreaker.getState(),
           wsStatus: this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status
       });
       // If WS is disconnected, no need to show SSE specific error, WS error takes precedence
       if (this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status === ConnectionStatus.CONNECTED) {
           ErrorHandler.handleConnectionError(
             `SSE Stream connection lost permanently. Circuit breaker may be open or max attempts reached. Reason: ${reason}`,
             ErrorSeverity.MEDIUM,
             'Data Stream (SSE)'
           );
           this.emit('connection_lost_permanently', { reason });
       }
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectTimer !== null) {
      this.logger.warn('SSE reconnect attempt skipped: Already in progress.');
      return; // Already trying to reconnect
    }

    // Double-check WebSocket status before scheduling reconnect
    if (this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status !== ConnectionStatus.CONNECTED) {
      this.logger.warn('SSE reconnect attempt cancelled: WebSocket is disconnected.');
      return;
    }

     // Check circuit breaker state again just before scheduling
    if (this.circuitBreaker.getState() === CircuitState.OPEN) {
        this.logger.error('SSE reconnect attempt cancelled: Circuit breaker is OPEN.');
        return;
    }


    if (this.reconnectAttempt >= this.maxReconnectAttempts) {
      this.logger.error(`SSE reconnect cancelled: Max reconnect attempts (${this.maxReconnectAttempts}) reached.`);
      this.emit('max_reconnect_attempts', { attempts: this.reconnectAttempt });
       ErrorHandler.handleConnectionError(
             `Failed to reconnect to SSE Stream after ${this.maxReconnectAttempts} attempts. Giving up.`,
             ErrorSeverity.HIGH,
             'Data Stream (SSE)'
           );
      return;
    }

    this.reconnectAttempt++;
    const delay = this.backoffStrategy.nextBackoffTime();
    this.logger.info(`Scheduling SSE reconnect attempt ${this.reconnectAttempt}/${this.maxReconnectAttempts} in ${delay}ms.`);

    this.emit('reconnecting', {
      attempt: this.reconnectAttempt,
      maxAttempts: this.maxReconnectAttempts,
      delay
    });

     // Update Unified State to show recovering status for SSE
     this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.RECOVERING,
        error: `Reconnecting (attempt ${this.reconnectAttempt})`,
        recoveryAttempts: this.reconnectAttempt
     });

    this.reconnectTimer = window.setTimeout(async () => {
      this.reconnectTimer = null;
      this.logger.info(`Executing scheduled SSE reconnect attempt ${this.reconnectAttempt}.`);
      // Connect will handle circuit breaker checks internally now
      const connected = await this.connect();
      if (!connected) {
        this.logger.warn(`SSE reconnect attempt ${this.reconnectAttempt} failed.`);
        // No need to call attemptReconnect explicitly here, failure handling within connect/establishConnection
        // or subsequent disconnects will trigger it if necessary and allowed.
      } else {
         this.logger.info(`SSE reconnect attempt ${this.reconnectAttempt} successful.`);
         // Reset recovery attempts in unified state on success
         this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
            recoveryAttempts: 0
         });
      }
    }, delay);

    // Use ErrorHandler for notifications
    ErrorHandler.handleConnectionError(
      `Reconnecting to market data stream (Attempt ${this.reconnectAttempt})...`,
      ErrorSeverity.LOW, // Low severity for transient info
      'Data Stream (SSE)'
    );
  }

  public close(): void {
     this.logger.info('SSE close requested.');
    this.stopReconnectTimer();

    if (this.eventSource) {
       this.logger.info('Closing existing EventSource.');
       this.removeMessageListeners(); // Remove listeners before closing
      this.eventSource.close();
      this.eventSource = null;
    }
     this.isConnecting = false; // Reset connecting flag

    // Update unified state only if not already disconnected
     const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
     if (sseState.status !== ConnectionStatus.DISCONNECTED) {
         this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
           status: ConnectionStatus.DISCONNECTED,
           error: 'Connection closed by client' // Or specific reason if available
         });
         this.emit('disconnected', { reason: 'manual_close' });
     }
  }

  private stopReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
       this.logger.info('Stopping SSE reconnect timer.');
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  public resetCircuitBreaker(): void {
    this.logger.warn('Manual reset of SSE circuit breaker requested.');
    this.circuitBreaker.reset();
     this.reconnectAttempt = 0; // Also reset reconnect attempts
     this.backoffStrategy.reset();
    // Optionally trigger a connection attempt immediately after reset
    // this.connect();
  }

  public getConnectionStatus(): {
    connected: boolean;
    connecting: boolean;
    circuitBreakerState: CircuitState; // Use enum type
    reconnectAttempt: number;
    maxReconnectAttempts: number;
  } {
    return {
      connected: !!this.eventSource && this.eventSource.readyState === EventSource.OPEN,
      connecting: this.isConnecting,
      circuitBreakerState: this.circuitBreaker.getState(),
      reconnectAttempt: this.reconnectAttempt,
      maxReconnectAttempts: this.maxReconnectAttempts
    };
  }

  public dispose(): void {
     this.logger.warn('Disposing SSEManager.');
    this.close();
    // Remove specific listeners if added elsewhere, e.g., WS state listener
    // this.unifiedState.off('websocket_state_change', this.handleWebSocketStateChange); // Assuming EventEmitter has `off`
    this.removeAllListeners(); // From EventEmitter base class
  }
}