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
import { CircuitBreaker, CircuitState } from '../../utils/circuit-breaker';
import { Logger } from '../../utils/logger';
import { Disposable } from '../../utils/disposable'; // <<< Import Disposable

export interface SSEOptions {
  reconnectMaxAttempts?: number;
  failureThreshold?: number;
  resetTimeoutMs?: number;
  preventAutoConnect?: boolean; // Add this new option
}

export class SSEManager extends EventEmitter implements Disposable { // <<< Implement Disposable
  private baseUrl: string;
  private tokenManager: TokenManager;
  private eventSource: EventSource | null = null;
  private reconnectTimer: number | null = null;
  private reconnectAttempt: number = 0;
  private maxReconnectAttempts: number;
  private backoffStrategy: BackoffStrategy;
  private isConnecting: boolean = false;
  private unifiedState: UnifiedConnectionState;
  private circuitBreaker: CircuitBreaker;
  private logger: Logger;
  private errorHandler: ErrorHandler;
  private isDisposed: boolean = false; // <<< Added dispose flag
  private preventAutoConnect: boolean = false; // Add this property

  constructor(
    tokenManager: TokenManager,
    unifiedState: UnifiedConnectionState,
    logger: Logger,
    errorHandler: ErrorHandler,
    options: SSEOptions = {}
  ) {
    super();
    this.logger = logger.createChild('SSEManager');
    this.baseUrl = config.sseBaseUrl;
    this.tokenManager = tokenManager;
    this.unifiedState = unifiedState;
    this.errorHandler = errorHandler;
    this.logger.info('SSE Manager Initializing...');
    this.maxReconnectAttempts = options.reconnectMaxAttempts ?? 15;
    this.backoffStrategy = new BackoffStrategy(1000, 30000);

    this.circuitBreaker = new CircuitBreaker(
        'sse-connection',
        options.failureThreshold ?? 5,
        options.resetTimeoutMs ?? 60000
    );

    this.circuitBreaker.onStateChange((name, oldState, newState, info) => {
        // <<< Check disposed flag in callback >>>
        if (this.isDisposed) return;
        this.logger.warn(`Circuit Breaker [${name}] state changed: ${oldState} -> ${newState}`, info);
        if (newState === CircuitState.OPEN) {
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
             const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
             const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
             if (sseState.status === ConnectionStatus.DISCONNECTED && wsState.status === ConnectionStatus.CONNECTED && this.tokenManager.isAuthenticated()) {
                 this.logger.info('SSE Circuit breaker closed, attempting reconnect...');
                 this.attemptReconnect(); // Triggers reconnect checks including disposed flag
             } else if (!this.tokenManager.isAuthenticated()) {
                 this.logger.info('SSE Circuit breaker closed, but user not authenticated. Skipping reconnect.');
             }
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
    // <<< Check disposed flag >>>
    if (this.isDisposed) return;

    this.logger.info(`Handling WebSocket state change in SSEManager: WS Status = ${state.status}`);
    const sseCurrentStatus = this.unifiedState.getServiceState(ConnectionServiceType.SSE).status;

    // If WebSocket connects, SSE is not connected/connecting, AND user is authenticated, try to connect SSE
    if (state.status === ConnectionStatus.CONNECTED &&
        sseCurrentStatus !== ConnectionStatus.CONNECTED &&
        sseCurrentStatus !== ConnectionStatus.CONNECTING &&
        this.tokenManager.isAuthenticated()) {
      this.logger.info('WebSocket connected and user authenticated. Triggering SSE connect attempt.');
      if(this.circuitBreaker.getState() === CircuitState.OPEN) {
          this.logger.warn('Resetting SSE circuit breaker due to successful WebSocket connection.');
          this.circuitBreaker.reset();
      }
      this.connect().catch(err => // connect() checks disposed flag
        this.logger.error('Failed to auto-connect SSE after WebSocket connected', { error: err })
      );
    }
    else if (state.status === ConnectionStatus.DISCONNECTED) {
       this.logger.warn('WebSocket disconnected. Closing SSE connection.');
       this.close('websocket_disconnected'); // close() checks disposed flag
       // Update state only if not disposed
       if (!this.isDisposed) {
           this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
             status: ConnectionStatus.DISCONNECTED,
             error: 'WebSocket disconnected'
           });
       }
    } else if (state.status === ConnectionStatus.CONNECTED && !this.tokenManager.isAuthenticated()) {
        this.logger.warn('WebSocket connected but user not authenticated. Skipping SSE connection.');
    }
  }

  // Initiates the connection process, respecting WebSocket status, auth, and circuit breaker
  public async connect(): Promise<boolean> {
    // <<< Check disposed flag early >>>
    if (this.isDisposed) {
        this.logger.error('SSE connect aborted: Manager is disposed.');
        return false;
    }
    this.logger.info('SSE connection attempt initiated.');

    // 1. Check WebSocket status
    const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    if (wsState.status !== ConnectionStatus.CONNECTED) {
      this.logger.error('SSE connect aborted: WebSocket is not connected.', { wsStatus: wsState.status });
      if (!this.isDisposed) this.emit('error', { error: 'Cannot connect SSE when WebSocket is disconnected' });
      return false;
    }

    // 2. Check Authentication token
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.error('SSE connect aborted: User is not authenticated.');
      if (!this.isDisposed) this.emit('error', { error: 'User not authenticated for SSE connection' });
      return false;
    }

    if (this.eventSource && this.eventSource.readyState === EventSource.OPEN) {
      this.logger.warn('SSE connect skipped: Already connected.');
      return true;
    }
    if (this.isConnecting) {
      this.logger.warn('SSE connect skipped: Connection already in progress.');
      // Return a promise that resolves based on the outcome of the ongoing attempt
      return new Promise<boolean>(resolve => {
          const successListener = () => resolve(true);
          const failListener = () => resolve(false);
          this.once('connected', successListener);
          this.once('connection_failed', failListener);
          // Consider cleanup if the component listening unmounts before resolution
      });
    }

    // 4. Use Circuit Breaker to execute the connection attempt
    try {
       return await this.circuitBreaker.execute(async () => {
           // <<< Check disposed flag inside execute >>>
           if (this.isDisposed) throw new Error('SSEManager disposed during circuit breaker execution');

           const token = await this.tokenManager.getAccessToken();
           if (!token) {
               this.logger.error('SSE connect aborted inside circuit breaker: No authentication token available.');
               throw new Error('No authentication token available for SSE');
           }
           // <<< Check disposed flag after await >>>
           if (this.isDisposed) throw new Error('SSEManager disposed after getting token');
           return await this.establishConnection(token); // establishConnection checks disposed flag
       });
    } catch (error: any) {
        // <<< Check disposed flag in error handling >>>
        if (this.isDisposed) {
            this.logger.warn("SSE connection failed, but manager was disposed. Ignoring error.", { error: error.message });
            return false;
        }
        this.logger.error('SSE connection failed via circuit breaker or internal error.', { error: error.message });
        this.handleConnectionFailure(error instanceof Error ? error.message : String(error));
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
      // <<< Check disposed flag early >>>
      if (this.isDisposed) {
          this.logger.error('SSE establishConnection aborted: Manager is disposed.');
          return false;
      }
      this.isConnecting = true;
      this.logger.info('Establishing SSE connection...');
      this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.CONNECTING,
        error: null,
        recoveryAttempts: this.reconnectAttempt
      });

      try {
        const fullUrl = `${this.baseUrl}?token=${token}`;
        this.logger.info('SSE Connection URL', { url: this.baseUrl });

        // Ensure any previous EventSource is fully closed and listeners removed
        if (this.eventSource) {
            this.logger.warn('Closing pre-existing EventSource instance before reconnecting.');
            this.close('reconnecting_new_instance'); // Use close to ensure cleanup
        }

        this.eventSource = new EventSource(fullUrl);
        this.logger.info('EventSource instance created.');

        return new Promise<boolean>((resolve) => {
          if (!this.eventSource) { // Should not happen, but safety check
              this.isConnecting = false;
              resolve(false);
              return;
          }
          this.eventSource.onopen = () => {
            // <<< Check disposed flag in callback >>>
            if (this.isDisposed) {
                this.logger.warn('SSE onopen fired, but manager is disposed. Closing connection.');
                this.close('disposed_on_open');
                resolve(false); // Indicate connection didn't truly establish for the current state
                return;
            }
            this.logger.info('SSE Connection Opened Successfully.');
            this.isConnecting = false;
            this.reconnectAttempt = 0;
            this.backoffStrategy.reset();

            this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
              status: ConnectionStatus.CONNECTED,
              lastConnected: Date.now(),
              error: null,
              recoveryAttempts: 0
            });
            this.emit('connected', { connected: true });
            resolve(true);
          };

          this.eventSource.onerror = (errorEvent) => {
            // <<< Check disposed flag in callback >>>
            if (this.isDisposed) {
                this.logger.warn('SSE onerror fired, but manager is disposed.');
                return;
            }
            this.logger.error('SSE onerror Event Triggered.', { readyState: this.eventSource?.readyState });

            // Handle errors primarily based on readyState
            const wasConnecting = this.isConnecting; // Capture state before potential changes
            this.isConnecting = false; // Assume connection attempt failed if error occurs

            if (this.eventSource?.readyState === EventSource.CLOSED) {
                 this.logger.warn('SSE onerror: Connection appears closed. Handling as disconnect.');
                 this.handleDisconnect('onerror_closed'); // Will check disposed flag
                 if (wasConnecting) {
                     this.emit('connection_failed', { error: 'SSE connection error during setup (closed)' });
                     resolve(false); // Resolve the promise if it was still pending
                 }
            } else if (this.eventSource?.readyState === EventSource.CONNECTING) {
                // Browser is attempting internal retries
                this.logger.warn('SSE onerror: Connection in connecting state (browser likely attempting internal retry).');
                const currentState = this.unifiedState.getServiceState(ConnectionServiceType.SSE).status;
                if (currentState !== ConnectionStatus.RECOVERING && currentState !== ConnectionStatus.CONNECTING) {
                     this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
                        status: ConnectionStatus.RECOVERING, // Use RECOVERING to indicate issue
                        error: 'SSE connection interrupted, attempting recovery...'
                     });
                }
                 if (wasConnecting) {
                     // If the initial connection attempt immediately goes into browser retry, fail it.
                     this.handleDisconnect('onerror_connecting');
                     this.emit('connection_failed', { error: 'SSE connection error during setup (connecting)' });
                     resolve(false);
                 }
            } else {
                 this.logger.error('SSE onerror: Unknown state during error.', { errorEvent });
                 // Treat unknown errors cautiously, handle as disconnect
                 this.handleDisconnect('onerror_unknown');
                 if (wasConnecting) {
                     this.emit('connection_failed', { error: 'SSE connection error during setup (unknown)' });
                     resolve(false);
                 }
            }
          };

          this.setupMessageListeners(); // Will check if eventSource exists
        });
      } catch (error: any) {
        // Catch synchronous errors during EventSource creation
        this.logger.error('SSE establishConnection caught synchronous error', { error: error.message });
        this.isConnecting = false;
        // Propagate the error to the circuit breaker/caller
        throw error;
      }
  }

  // Sets up listeners for named events from the SSE stream
  private setupMessageListeners(): void {
    if (!this.eventSource) return; // <<< Check if EventSource exists
    this.logger.info('Setting up SSE message listeners.');

    // Generic message handler
    this.eventSource.onmessage = (event: MessageEvent) => {
       if (this.isDisposed) return; // <<< Check disposed flag
       this.logger.debug('SSE generic message received', { data: event.data });
        try {
            const parsedData = JSON.parse(event.data);
            this.emit('message', { type: 'message', data: parsedData });
        } catch (parseError: any) {
            this.logger.error('Failed to parse generic SSE message', { error: parseError.message, rawData: event.data });
            if (!this.isDisposed) this.emit('error', { error: 'Failed to parse SSE message', originalError: parseError, rawData: event.data });
        }
    };

    // Specific event listeners
    const addSpecificListener = (eventName: string) => {
        if (!this.eventSource) return;
        this.eventSource.addEventListener(eventName, (event: MessageEvent) => {
            if (this.isDisposed) return; // <<< Check disposed flag
            this.logger.debug(`SSE ${eventName} event received`);
            try {
                const data = JSON.parse(event.data);
                this.emit(eventName, data); // Emit with specific event name
                this.emit('message', { type: eventName, data }); // Also emit as generic message
            } catch (error: any) {
                 this.logger.error(`Failed to parse ${eventName} event`, { error: error.message, rawData: event.data });
                 if (!this.isDisposed) this.emit('error', { error: `Failed to parse ${eventName} event`, originalError: error, rawData: event.data });
            }
        });
    };

    addSpecificListener('exchange-data');
    addSpecificListener('order-update');
    addSpecificListener('error-event'); // Listen for server-sent errors
  }

  // Removes all message listeners from the current EventSource instance
  private removeMessageListeners(): void {
       if (!this.eventSource) return;
       this.logger.info('Removing SSE message listeners.');
       // Nullify standard handlers
       this.eventSource.onmessage = null;
       this.eventSource.onerror = null;
       this.eventSource.onopen = null;
       // Remove specific listeners using a dummy handler (common pattern)
       const dummyHandler = () => {};
       try {
           this.eventSource.removeEventListener('exchange-data', dummyHandler);
           this.eventSource.removeEventListener('order-update', dummyHandler);
           this.eventSource.removeEventListener('error-event', dummyHandler);
       } catch(e) {
           this.logger.warn("Minor error during removeEventListener (might be expected if listener wasn't added)", e);
       }
  }

  // Handles connection failures, logging and notifying via ErrorHandler
  private handleConnectionFailure(errorMessage: string) {
    // <<< Check disposed flag early >>>
    if (this.isDisposed) return;
    this.logger.error(`SSE Connection Failure: ${errorMessage}`);
    this.isConnecting = false;

    this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
      status: ConnectionStatus.DISCONNECTED,
      error: `Connection failure: ${errorMessage}`
    });

    this.emit('connection_failed', { error: errorMessage });

    // Use injected errorHandler instance
     if (this.circuitBreaker.getState() === CircuitState.OPEN) {
         this.errorHandler.handleConnectionError(
            `SSE connection failed and circuit breaker is OPEN. Attempts suspended. Reason: ${errorMessage}`,
            ErrorSeverity.HIGH,
            'Data Stream (SSE)'
         );
     } else {
          this.errorHandler.handleConnectionError(
            `SSE connection failed. Reason: ${errorMessage}`,
            ErrorSeverity.MEDIUM,
            'Data Stream (SSE)'
         );
     }
  }

  // Handles disconnection events, updates state, and potentially triggers reconnect attempts
  private handleDisconnect(reason: string = 'unknown'): void {
    // <<< Check disposed flag early >>>
    if (this.isDisposed) return;

    this.logger.warn(`SSE Disconnected. Reason: ${reason}`);
    this.isConnecting = false; // Ensure connecting flag is reset

    // Update unified state if not already disconnected
    const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
    if (sseState.status !== ConnectionStatus.DISCONNECTED) {
         this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
           status: ConnectionStatus.DISCONNECTED,
           error: `Connection lost (${reason})`
         });
          this.emit('disconnected', { reason });
    }

    // --- Reconnect Logic ---
    const shouldAttemptReconnect = reason !== 'websocket_disconnected' && reason !== 'manual_close' && reason !== 'dispose' && reason !== 'reconnecting_new_instance';
    const isWebSocketConnected = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status === ConnectionStatus.CONNECTED;
    const circuitIsOpen = this.circuitBreaker.getState() === CircuitState.OPEN;
    const isAuthenticated = this.tokenManager.isAuthenticated();

    if (shouldAttemptReconnect && isWebSocketConnected && isAuthenticated && !circuitIsOpen) {
      this.logger.info('Attempting SSE reconnect after disconnect.');
      this.attemptReconnect(); // Checks disposed flag internally
    } else {
       // Log why reconnect wasn't attempted
       this.logger.warn('Not attempting SSE reconnect.', {
           shouldAttemptReconnect,
           isWebSocketConnected,
           isAuthenticated,
           circuitIsOpen,
           reason
       });
       // <<< FIX: Removed isNormalClosure check >>>
       if (!isAuthenticated /* && !isNormalClosure */) { // Check only authentication status
           this.logger.info('Resetting SSE reconnect counters due to lack of authentication.');
           this.reconnectAttempt = 0;
           this.backoffStrategy.reset();
       } else if (isWebSocketConnected && (circuitIsOpen || this.reconnectAttempt >= this.maxReconnectAttempts)) {
           this.errorHandler.handleConnectionError(
             `SSE Stream connection lost permanently. Circuit breaker may be open or max attempts reached. Reason: ${reason}`,
             ErrorSeverity.MEDIUM, // Maybe HIGH if data is critical
             'Data Stream (SSE)'
           );
           this.emit('connection_lost_permanently', { reason });
       }
    }
  }

  // Manages the reconnection attempt scheduling and execution
  private attemptReconnect(): void {
    // *** ADD CHECK: Abort if disposed or timer already active ***
    if (this.isDisposed || this.reconnectTimer !== null) {
        if (this.reconnectTimer !== null) this.logger.warn('SSE reconnect attempt skipped: Timer already active or manager disposed.');
        return;
    }

    // +++ AUTHENTICATION CHECK +++
    if (!this.tokenManager.isAuthenticated()) {
        this.logger.error('SSE reconnect attempt cancelled: User is not authenticated.');
        // Don't update unifiedState recovery here, let the disconnect handler manage it
        this.reconnectAttempt = 0;
        this.backoffStrategy.reset();
        return;
    }
    // +++ END CHECK +++

    // --- Pre-checks before scheduling ---
    if (this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status !== ConnectionStatus.CONNECTED) {
      this.logger.warn('SSE reconnect attempt cancelled: WebSocket is disconnected.');
      return;
    }
    if (this.circuitBreaker.getState() === CircuitState.OPEN) {
        this.logger.error('SSE reconnect attempt cancelled: Circuit breaker is OPEN.');
        return;
    }
    if (this.reconnectAttempt >= this.maxReconnectAttempts) {
      this.logger.error(`SSE reconnect cancelled: Max reconnect attempts (${this.maxReconnectAttempts}) reached.`);
      this.emit('max_reconnect_attempts', { attempts: this.reconnectAttempt });
       this.errorHandler.handleConnectionError(
             `Failed to reconnect to SSE Stream after ${this.maxReconnectAttempts} attempts. Giving up.`,
             ErrorSeverity.HIGH,
             'Data Stream (SSE)'
           );
      // Update state to reflect permanent failure only if not disposed
      if (!this.isDisposed) {
          this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
              status: ConnectionStatus.DISCONNECTED,
              error: `Max reconnect attempts reached (${this.maxReconnectAttempts})`,
              recoveryAttempts: this.reconnectAttempt
          });
      }
      return;
    }

    // --- Schedule the reconnect attempt ---
    this.reconnectAttempt++;
    const delay = this.backoffStrategy.nextBackoffTime();
    this.logger.info(`Scheduling SSE reconnect attempt ${this.reconnectAttempt}/${this.maxReconnectAttempts} in ${delay}ms.`);

    this.emit('reconnecting', {
      attempt: this.reconnectAttempt,
      maxAttempts: this.maxReconnectAttempts,
      delay
    });

     this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.RECOVERING,
        error: `Reconnecting (attempt ${this.reconnectAttempt})`,
        recoveryAttempts: this.reconnectAttempt
     });

    this.reconnectTimer = window.setTimeout(async () => {
      this.reconnectTimer = null;
      // *** ADD CHECK: Abort if disposed before timer fires ***
      if (this.isDisposed) {
          this.logger.warn('Reconnect timer fired, but SSEManager is disposed. Aborting connect attempt.');
          return;
      }
      this.logger.info(`Executing scheduled SSE reconnect attempt ${this.reconnectAttempt}.`);
      const connected = await this.connect(); // connect checks disposed flag
      if (!connected && !this.isDisposed) { // Check disposed again after await
        this.logger.warn(`SSE reconnect attempt ${this.reconnectAttempt} failed.`);
        // Further failure handling (next attempt) is managed by connect() -> handleDisconnect()
      } else if(connected && !this.isDisposed) {
         this.logger.info(`SSE reconnect attempt ${this.reconnectAttempt} successful.`);
         // Success handling (resetting attempts etc.) done in establishConnection -> onopen
      }
    }, delay);

    this.errorHandler.handleConnectionError(
      `Reconnecting to data stream (Attempt ${this.reconnectAttempt})...`,
      ErrorSeverity.LOW,
      'Data Stream (SSE)'
    );
  }

  // Closes the SSE connection and stops any reconnection attempts
  public close(reason?: string): void { // <<< Accept optional reason
    // <<< Check disposed flag (allow close even if disposing) >>>
    // if (this.isDisposed && reason !== 'dispose') return;

     this.logger.info(`SSE close requested. Reason: ${reason ?? 'N/A'}`);
     this.stopReconnectTimer(); // Stop timer first

    if (this.eventSource) {
       this.logger.info('Closing existing EventSource.');
       this.removeMessageListeners(); // Remove listeners before closing
       // Explicitly nullify handlers to be safe
       this.eventSource.onerror = null;
       this.eventSource.onopen = null;
       this.eventSource.onmessage = null;
       this.eventSource.close();
       this.eventSource = null;
    }
    this.isConnecting = false; // Ensure connecting flag is reset

    // Update state only if not already disconnected *and* not disposing
     if (!this.isDisposed) {
        const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
        if (sseState.status !== ConnectionStatus.DISCONNECTED) {
            this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
              status: ConnectionStatus.DISCONNECTED,
              error: `Connection closed (${reason ?? 'N/A'})`
            });
            this.emit('disconnected', { reason });
        }
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
    // <<< Check disposed flag >>>
    if (this.isDisposed) {
        this.logger.warn('Reset circuit breaker ignored: SSEManager disposed.');
        return;
    }
    this.logger.warn('Manual reset of SSE circuit breaker requested.');
    this.circuitBreaker.reset();
    this.reconnectAttempt = 0; // Reset attempts on manual breaker reset
    this.backoffStrategy.reset();
  }

  // Returns the current status of the SSE connection and related mechanisms
  public getConnectionStatus(): {
    connected: boolean;
    connecting: boolean;
    circuitBreakerState: CircuitState;
    reconnectAttempt: number;
    maxReconnectAttempts: number;
  } {
    // <<< Handle disposed state >>>
    if (this.isDisposed) {
        return {
            connected: false,
            connecting: false,
            circuitBreakerState: this.circuitBreaker.getState(), // Can still report state
            reconnectAttempt: this.reconnectAttempt,
            maxReconnectAttempts: this.maxReconnectAttempts,
        };
    }
    const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
    return {
      connected: sseState.status === ConnectionStatus.CONNECTED,
      connecting: sseState.status === ConnectionStatus.CONNECTING || this.isConnecting, // Use internal flag too
      circuitBreakerState: this.circuitBreaker.getState(),
      reconnectAttempt: this.reconnectAttempt,
      maxReconnectAttempts: this.maxReconnectAttempts
    };
  }

  /**
   * Cleans up resources when the SSEManager is no longer needed.
   * <<< REFACTORED dispose method >>>
   */
  public dispose(): void {
    // *** Check and set disposed flag immediately ***
    if (this.isDisposed) {
        this.logger.warn('SSEManager already disposed.');
        return;
    }
    this.logger.warn('Disposing SSEManager.');
    this.isDisposed = true; // Set flag early

    // *** Unsubscribe from external events FIRST ***
    // Ensure listener removal happens reliably
    try {
        // Assuming unifiedState still exists, attempt removal
        this.unifiedState.off('websocket_state_change', this.handleWebSocketStateChange.bind(this));
    } catch (e) {
        this.logger.error("Error unsubscribing from unifiedState during dispose", e);
    }


    // *** Close connection and stop timers ***
    this.close('dispose'); // Ensures EventSource is closed and timer is stopped

    // *** Remove internal listeners ***
    this.removeAllListeners(); // From EventEmitter base

    // *** Optional: Clear references ***
    // Assigning null might help GC but isn't strictly necessary if the instance itself is dereferenced
    // this.tokenManager = null;
    // this.unifiedState = null;
    // this.errorHandler = null;
    // this.circuitBreaker = null;
    // this.backoffStrategy = null;


    this.logger.info('SSEManager dispose complete.');
  }

   /**
   * Implements the [Symbol.dispose] method for the Disposable interface.
   */
  [Symbol.dispose](): void {
      this.dispose();
  }
}