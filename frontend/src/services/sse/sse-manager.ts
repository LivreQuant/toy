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
  private errorHandler: ErrorHandler; // Store the ErrorHandler instance

  constructor(
    tokenManager: TokenManager,
    unifiedState: UnifiedConnectionState,
    logger: Logger, // Inject Logger
    errorHandler: ErrorHandler, // Inject ErrorHandler
    options: SSEOptions = {}
  ) {
    super();
    this.logger = logger.createChild('SSEManager'); // Create child logger
    this.baseUrl = config.sseBaseUrl;
    this.tokenManager = tokenManager;
    this.unifiedState = unifiedState;
    this.errorHandler = errorHandler; // Store injected instance
    this.logger.info('SSE Manager Initializing...');
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
            // Use the stored errorHandler instance
            this.errorHandler.handleConnectionError(
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

  // Handles changes in the WebSocket connection state to coordinate SSE connection
  private handleWebSocketStateChange({ state }: { service: ConnectionServiceType, state: ServiceState }): void {
    this.logger.info(`Handling WebSocket state change in SSEManager: WS Status = ${state.status}`);
    const sseCurrentStatus = this.unifiedState.getServiceState(ConnectionServiceType.SSE).status;

    // If WebSocket connects and SSE is not already connected/connecting, try to connect SSE
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
    }
    // If WebSocket disconnects, close the SSE connection
    else if (state.status === ConnectionStatus.DISCONNECTED) {
       this.logger.warn('WebSocket disconnected. Closing SSE connection.');
      this.close('websocket_disconnected'); // Pass reason for closing
       // Explicitly set SSE state to disconnected due to WS disconnect
      this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.DISCONNECTED,
        error: 'WebSocket disconnected'
      });
    }
  }

  // Initiates the connection process, respecting WebSocket status, auth, and circuit breaker
  public async connect(): Promise<boolean> {
    this.logger.info('SSE connection attempt initiated.');

    // 1. Check WebSocket status
    const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    if (wsState.status !== ConnectionStatus.CONNECTED) {
      this.logger.error('SSE connect aborted: WebSocket is not connected.', { wsStatus: wsState.status });
      this.emit('error', { error: 'Cannot connect SSE when WebSocket is disconnected' });
      return false;
    }

    // 2. Check Authentication token
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      this.logger.error('SSE connect aborted: No authentication token available.');
      this.emit('error', { error: 'No authentication token available for SSE' });
      return false;
    }

    // 3. Check if already connected or connecting
    if (this.eventSource && this.eventSource.readyState === EventSource.OPEN) {
      this.logger.warn('SSE connect skipped: Already connected.');
      return true;
    }
    if (this.isConnecting) {
      this.logger.warn('SSE connect skipped: Connection already in progress.');
      // Wait for the current attempt to finish
      return new Promise<boolean>(resolve => {
        this.once('connected', () => resolve(true));
        this.once('connection_failed', () => resolve(false));
      });
    }

    // 4. Use Circuit Breaker to execute the connection attempt
    try {
       return await this.circuitBreaker.execute(async () => {
           // Call the internal method to establish the connection
           return await this.establishConnection(token);
       });
    } catch (error: any) {
        // Handle errors from circuit breaker (OPEN state) or establishConnection
        this.logger.error('SSE connection failed via circuit breaker or internal error.', { error: error.message });
        this.handleConnectionFailure(error instanceof Error ? error.message : String(error)); // Pass error message
        // Ensure state is updated
        this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
            status: ConnectionStatus.DISCONNECTED,
            error: `Connection failed: ${error.message}`
        });
        this.emit('connection_failed', { error: error.message });
        return false;
    }
  }

  // Internal method containing the core EventSource creation and handling logic
  private async establishConnection(token: string): Promise<boolean> {
      this.isConnecting = true;
      this.logger.info('Establishing SSE connection...');
      this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.CONNECTING,
        error: null,
        recoveryAttempts: this.reconnectAttempt // Reflect current attempt count
      });

      try {
        const fullUrl = `${this.baseUrl}?token=${token}`;
        this.logger.info('SSE Connection URL', { url: this.baseUrl }); // Log base URL only

        // Close existing EventSource if any before creating a new one
        if (this.eventSource) {
            this.logger.warn('Closing pre-existing EventSource instance before reconnecting.');
            this.eventSource.close();
            this.removeMessageListeners(); // Clean up old listeners
        }

        this.eventSource = new EventSource(fullUrl);
        this.logger.info('EventSource instance created.');

        // Return a promise that resolves/rejects based on EventSource events
        return new Promise<boolean>((resolve) => {
          // --- Success Handler ---
          this.eventSource!.onopen = () => {
            this.logger.info('SSE Connection Opened Successfully.');
            this.isConnecting = false;
            this.reconnectAttempt = 0; // Reset on successful connection
            this.backoffStrategy.reset();
            // Circuit breaker is reset automatically by the execute wrapper on success

            this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
              status: ConnectionStatus.CONNECTED,
              lastConnected: Date.now(),
              error: null,
              recoveryAttempts: 0 // Reset recovery attempts in state
            });
            this.emit('connected', { connected: true });
            resolve(true); // Resolve the promise indicating success
          };

          // --- Error Handler ---
          this.eventSource!.onerror = (errorEvent) => {
            // This handler is triggered for various network issues,
            // including temporary blips where the browser might reconnect automatically.
            this.logger.error('SSE onerror Event Triggered.', { readyState: this.eventSource?.readyState });

            // Check if the connection is definitively closed
            if (this.eventSource?.readyState === EventSource.CLOSED) {
                 this.logger.warn('SSE onerror: Connection appears closed. Handling as disconnect.');
                 // This is a definite disconnect, trigger full disconnect handling
                 this.handleDisconnect('onerror_closed');

                 // If we were in the middle of the initial connection attempt, reject the promise
                 if (this.isConnecting) {
                     this.isConnecting = false; // Reset connecting flag
                     this.emit('connection_failed', { error: 'SSE connection error during setup' });
                     resolve(false); // Resolve promise indicating initial connection failure
                 }
            } else if (this.eventSource?.readyState === EventSource.CONNECTING) {
                // Browser is attempting reconnect internally. Log it, but don't trigger full reconnect logic yet.
                this.logger.warn('SSE onerror: Connection in connecting state (browser likely attempting internal retry).');
                // Update state to RECOVERING if not already connecting/recovering
                const currentState = this.unifiedState.getServiceState(ConnectionServiceType.SSE).status;
                if (currentState === ConnectionStatus.CONNECTED) {
                     this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
                        status: ConnectionStatus.RECOVERING,
                        error: 'SSE connection interrupted, attempting recovery...'
                     });
                }
            } else {
                 // Log unexpected states
                 this.logger.error('SSE onerror: Unknown state during error.', { errorEvent });
            }
          };

          // Setup listeners for specific message types from the server
          this.setupMessageListeners();
        });
      } catch (error: any) {
        // Catch synchronous errors during EventSource creation (unlikely but possible)
        this.logger.error('SSE establishConnection caught synchronous error', { error: error.message });
        this.isConnecting = false;
        // Throw the error so the circuit breaker's execute wrapper can catch it
        throw error;
      }
  }

  // Sets up listeners for named events from the SSE stream
  private setupMessageListeners(): void {
    if (!this.eventSource) return;
    this.logger.info('Setting up SSE message listeners.');

    // Generic 'message' event (if server sends unnamed events)
    this.eventSource.onmessage = (event: MessageEvent) => {
       this.logger.debug('SSE generic message received', { data: event.data }); // Use debug level
        try {
            const parsedData = JSON.parse(event.data);
            this.emit('message', { type: 'message', data: parsedData });
        } catch (parseError: any) {
            this.logger.error('Failed to parse generic SSE message', { error: parseError.message, rawData: event.data });
            this.emit('error', { error: 'Failed to parse SSE message', originalError: parseError, rawData: event.data });
        }
    };

    // Listener for 'exchange-data' named events
    this.eventSource.addEventListener('exchange-data', (event: MessageEvent) => {
       this.logger.debug('SSE exchange-data event received'); // Use debug level, don't log data
        try {
            const data = JSON.parse(event.data);
            this.emit('exchange-data', data); // Emit specific event
            this.emit('message', { type: 'exchange-data', data }); // Also emit generic message
        } catch (error: any) {
             this.logger.error('Failed to parse exchange-data event', { error: error.message, rawData: event.data });
             this.emit('error', { error: 'Failed to parse exchange-data event', originalError: error, rawData: event.data });
        }
    });

    // Example: Listener for a custom 'order-update' event
     this.eventSource.addEventListener('order-update', (event: MessageEvent) => {
       this.logger.debug('SSE order-update event received'); // Use debug level
        try {
            const data = JSON.parse(event.data);
            this.emit('order-update', data); // Emit specific event
            this.emit('message', { type: 'order-update', data }); // Also emit generic message
        } catch (error: any) {
             this.logger.error('Failed to parse order-update event', { error: error.message, rawData: event.data });
             this.emit('error', { error: 'Failed to parse order-update event', originalError: error, rawData: event.data });
        }
    });

    // Listener for potential 'error-event' sent explicitly by the server
    this.eventSource.addEventListener('error-event', (event: MessageEvent) => {
       this.logger.error('SSE server-sent error event received', { data: event.data });
        try {
            const errorData = JSON.parse(event.data);
            this.emit('server_error', errorData); // Emit specific server error event
            this.emit('error', { type: 'server_error', data: errorData }); // Also emit generic error
        } catch (error) {
            this.emit('error', { error: 'Server reported an unparseable error', rawData: event.data });
        }
    });
  }

  // Removes all message listeners from the current EventSource instance
  private removeMessageListeners(): void {
       if (!this.eventSource) return;
       this.logger.info('Removing SSE message listeners.');
       this.eventSource.onmessage = null;
       this.eventSource.onerror = null; // Also remove the error handler
       this.eventSource.onopen = null; // Also remove the open handler
       // Use a dummy handler for removeEventListener, as the actual handler reference isn't stored
       const dummyHandler = () => {};
       this.eventSource.removeEventListener('exchange-data', dummyHandler);
       this.eventSource.removeEventListener('order-update', dummyHandler);
       this.eventSource.removeEventListener('error-event', dummyHandler);
       // Remove other custom listeners here
  }

  // Handles connection failures, logging and notifying via ErrorHandler
  private handleConnectionFailure(errorMessage: string) {
    this.logger.error(`SSE Connection Failure: ${errorMessage}`); // Use error level
     this.isConnecting = false; // Ensure connecting flag is reset

    // Update unified state (might be redundant if already set in connect's catch block)
    this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
      status: ConnectionStatus.DISCONNECTED,
      error: `Connection failure: ${errorMessage}`
    });

    // Emit a specific failure event
    this.emit('connection_failed', { error: errorMessage });

     // Check if circuit breaker is open and notify via ErrorHandler
     if (this.circuitBreaker.getState() === CircuitState.OPEN) {
         // *** FIX: Use instance method ***
         this.errorHandler.handleConnectionError(
            `SSE connection failed and circuit breaker is OPEN. Attempts suspended. Reason: ${errorMessage}`,
            ErrorSeverity.HIGH,
            'Data Stream (SSE)'
         );
     } else {
          // *** FIX: Use instance method ***
          this.errorHandler.handleConnectionError(
            `SSE connection failed. Reason: ${errorMessage}`,
            ErrorSeverity.MEDIUM, // Medium severity for non-circuit-open failures
            'Data Stream (SSE)'
         );
     }
  }

  // Handles disconnection events, updates state, and potentially triggers reconnect attempts
  private handleDisconnect(reason: string = 'unknown'): void {
    this.logger.warn(`SSE Disconnected. Reason: ${reason}`);
     this.isConnecting = false; // Ensure connecting flag is reset

    // Determine if reconnection should be attempted
    // Don't reconnect if WS is down or if closed manually/by WS handler
    const shouldAttemptReconnect = reason !== 'websocket_disconnected' && reason !== 'manual_close';
    const isWebSocketConnected = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status === ConnectionStatus.CONNECTED;
    const circuitIsOpen = this.circuitBreaker.getState() === CircuitState.OPEN;

    // Update unified state immediately if not already disconnected
     const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
     if (sseState.status !== ConnectionStatus.DISCONNECTED) {
         this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
           status: ConnectionStatus.DISCONNECTED,
           error: `Connection lost (${reason})`
         });
          this.emit('disconnected', { reason }); // Emit disconnect event
     }

    // Attempt to reconnect if appropriate conditions are met
    if (shouldAttemptReconnect && isWebSocketConnected && !circuitIsOpen) {
      this.logger.info('Attempting SSE reconnect after disconnect.');
      this.attemptReconnect();
    } else {
       // Log why reconnect is not being attempted
       this.logger.warn('Not attempting SSE reconnect.', {
           shouldAttemptReconnect,
           isWebSocketConnected,
           circuitIsOpen,
           reason
       });
       // If WebSocket is still connected, it means SSE failed independently or reached max attempts/circuit open
       if (isWebSocketConnected) {
           // *** FIX: Use instance method ***
           this.errorHandler.handleConnectionError(
             `SSE Stream connection lost permanently. Circuit breaker may be open or max attempts reached. Reason: ${reason}`,
             ErrorSeverity.MEDIUM, // Medium, as WS is still up
             'Data Stream (SSE)'
           );
           this.emit('connection_lost_permanently', { reason });
       }
       // If WS is disconnected, the primary error is handled by the WS manager
    }
  }

  // Manages the reconnection attempt scheduling and execution
  private attemptReconnect(): void {
    // Prevent concurrent reconnect timers
    if (this.reconnectTimer !== null) {
      this.logger.warn('SSE reconnect attempt skipped: Timer already active.');
      return;
    }

    // Pre-checks before scheduling
    if (this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status !== ConnectionStatus.CONNECTED) {
      this.logger.warn('SSE reconnect attempt cancelled: WebSocket is disconnected.');
      return;
    }
    if (this.circuitBreaker.getState() === CircuitState.OPEN) {
        this.logger.error('SSE reconnect attempt cancelled: Circuit breaker is OPEN.');
        // Notification handled by circuit breaker state change
        return;
    }
    if (this.reconnectAttempt >= this.maxReconnectAttempts) {
      this.logger.error(`SSE reconnect cancelled: Max reconnect attempts (${this.maxReconnectAttempts}) reached.`);
      this.emit('max_reconnect_attempts', { attempts: this.reconnectAttempt });
       // *** FIX: Use instance method ***
       this.errorHandler.handleConnectionError(
             `Failed to reconnect to SSE Stream after ${this.maxReconnectAttempts} attempts. Giving up.`,
             ErrorSeverity.HIGH, // High severity as we are giving up
             'Data Stream (SSE)'
           );
      return;
    }

    // Schedule the reconnect attempt
    this.reconnectAttempt++;
    const delay = this.backoffStrategy.nextBackoffTime();
    this.logger.info(`Scheduling SSE reconnect attempt ${this.reconnectAttempt}/${this.maxReconnectAttempts} in ${delay}ms.`);

    // Emit event for UI feedback
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

    // Set the timer to execute the connection attempt
    this.reconnectTimer = window.setTimeout(async () => {
      this.reconnectTimer = null; // Clear timer ID before attempting
      this.logger.info(`Executing scheduled SSE reconnect attempt ${this.reconnectAttempt}.`);
      // connect() handles circuit breaker checks and further logic
      const connected = await this.connect();
      if (!connected) {
        this.logger.warn(`SSE reconnect attempt ${this.reconnectAttempt} failed.`);
        // Failure handling (including potential next attempt) is managed by connect() -> establishConnection() -> onerror -> handleDisconnect()
      } else {
         this.logger.info(`SSE reconnect attempt ${this.reconnectAttempt} successful.`);
         // State is updated within establishConnection on success
      }
    }, delay);

    // Use ErrorHandler for low-severity notification about the attempt starting
    // *** FIX: Use instance method ***
    this.errorHandler.handleConnectionError(
      `Reconnecting to data stream (Attempt ${this.reconnectAttempt})...`,
      ErrorSeverity.LOW, // Low severity for transient info
      'Data Stream (SSE)'
    );
  }

  // Closes the SSE connection and stops any reconnection attempts
  public close(reason: string = 'manual_close'): void {
     this.logger.info(`SSE close requested. Reason: ${reason}`);
    this.stopReconnectTimer(); // Stop any pending reconnect attempts

    if (this.eventSource) {
       this.logger.info('Closing existing EventSource.');
       this.removeMessageListeners(); // Remove listeners before closing
       // Setting onerror/onopen/onmessage to null might be redundant if removeMessageListeners works
       this.eventSource.onerror = null;
       this.eventSource.onopen = null;
       this.eventSource.onmessage = null;
       this.eventSource.close(); // Close the connection
       this.eventSource = null; // Nullify the reference
    }
     this.isConnecting = false; // Reset connecting flag

    // Update unified state only if not already disconnected
     const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
     if (sseState.status !== ConnectionStatus.DISCONNECTED) {
         this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
           status: ConnectionStatus.DISCONNECTED,
           error: `Connection closed (${reason})`
         });
         this.emit('disconnected', { reason });
     }
  }

  // Clears the reconnection timer if it's active
  private stopReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
       this.logger.info('Stopping SSE reconnect timer.');
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  // Manually resets the circuit breaker, allowing immediate connection attempts
  public resetCircuitBreaker(): void {
    this.logger.warn('Manual reset of SSE circuit breaker requested.');
    this.circuitBreaker.reset();
     this.reconnectAttempt = 0; // Also reset reconnect attempts count
     this.backoffStrategy.reset(); // Reset backoff strategy
    // Optionally trigger a connection attempt immediately after reset
    // this.logger.info('Attempting SSE connection immediately after circuit breaker reset.');
    // this.connect();
  }

  // Returns the current status of the SSE connection and related mechanisms
  public getConnectionStatus(): {
    connected: boolean;
    connecting: boolean;
    circuitBreakerState: CircuitState; // Use enum type
    reconnectAttempt: number;
    maxReconnectAttempts: number;
  } {
    const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
    return {
      connected: sseState.status === ConnectionStatus.CONNECTED,
      connecting: sseState.status === ConnectionStatus.CONNECTING,
      circuitBreakerState: this.circuitBreaker.getState(),
      reconnectAttempt: this.reconnectAttempt, // Use internal counter
      maxReconnectAttempts: this.maxReconnectAttempts
    };
  }

  // Cleans up resources when the SSEManager is no longer needed
  public dispose(): void {
     this.logger.warn('Disposing SSEManager.');
    // Remove listener for WebSocket state changes
    this.unifiedState.off('websocket_state_change', this.handleWebSocketStateChange.bind(this)); // Ensure 'off' method exists and works
    this.close('dispose'); // Close connection and stop timers
    this.removeAllListeners(); // From EventEmitter base class
    // Optional: Nullify references if needed, though GC should handle it
    // this.tokenManager = null;
    // this.unifiedState = null;
    // this.errorHandler = null;
    // this.logger = null;
  }
}
