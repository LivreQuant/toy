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

export interface SSEOptions {
  reconnectMaxAttempts?: number;
  failureThreshold?: number;
  resetTimeoutMs?: number;
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
  private circuitBreaker: CircuitBreaker;
  private logger: Logger;
  private errorHandler: ErrorHandler;

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
             // *** Check auth before reconnecting after circuit closed ***
             const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
             const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
             if (sseState.status === ConnectionStatus.DISCONNECTED && wsState.status === ConnectionStatus.CONNECTED && this.tokenManager.isAuthenticated()) {
                 this.logger.info('SSE Circuit breaker closed, attempting reconnect...');
                 this.attemptReconnect();
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

    this.unifiedState.on('websocket_state_change', this.handleWebSocketStateChange.bind(this));
  }

  // Handles changes in the WebSocket connection state to coordinate SSE connection
  private handleWebSocketStateChange({ state }: { service: ConnectionServiceType, state: ServiceState }): void {
    this.logger.info(`Handling WebSocket state change in SSEManager: WS Status = ${state.status}`);
    const sseCurrentStatus = this.unifiedState.getServiceState(ConnectionServiceType.SSE).status;

    // If WebSocket connects, SSE is not connected/connecting, AND user is authenticated, try to connect SSE
    if (state.status === ConnectionStatus.CONNECTED &&
        sseCurrentStatus !== ConnectionStatus.CONNECTED &&
        sseCurrentStatus !== ConnectionStatus.CONNECTING &&
        this.tokenManager.isAuthenticated()) { // <-- Added auth check
      this.logger.info('WebSocket connected and user authenticated. Triggering SSE connect attempt.');
      if(this.circuitBreaker.getState() === CircuitState.OPEN) {
          this.logger.warn('Resetting SSE circuit breaker due to successful WebSocket connection.');
          this.circuitBreaker.reset();
      }
      this.connect().catch(err =>
        this.logger.error('Failed to auto-connect SSE after WebSocket connected', { error: err })
      );
    }
    else if (state.status === ConnectionStatus.DISCONNECTED) {
       this.logger.warn('WebSocket disconnected. Closing SSE connection.');
       this.close('websocket_disconnected');
       this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.DISCONNECTED,
        error: 'WebSocket disconnected'
       });
    } else if (state.status === ConnectionStatus.CONNECTED && !this.tokenManager.isAuthenticated()) {
        this.logger.warn('WebSocket connected but user not authenticated. Skipping SSE connection.');
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

    // 2. Check Authentication token (using isAuthenticated for simplicity)
    // getAccessToken is called within establishConnection if needed
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.error('SSE connect aborted: User is not authenticated.');
      this.emit('error', { error: 'User not authenticated for SSE connection' });
      return false;
    }

    if (this.eventSource && this.eventSource.readyState === EventSource.OPEN) {
      this.logger.warn('SSE connect skipped: Already connected.');
      return true;
    }
    if (this.isConnecting) {
      this.logger.warn('SSE connect skipped: Connection already in progress.');
      return new Promise<boolean>(resolve => {
        this.once('connected', () => resolve(true));
        this.once('connection_failed', () => resolve(false));
      });
    }

    // 4. Use Circuit Breaker to execute the connection attempt
    try {
       return await this.circuitBreaker.execute(async () => {
           // Need to get token *inside* the execute block in case it was refreshed
           const token = await this.tokenManager.getAccessToken();
           if (!token) {
               this.logger.error('SSE connect aborted inside circuit breaker: No authentication token available.');
               throw new Error('No authentication token available for SSE'); // Throw to fail the circuit breaker attempt
           }
           return await this.establishConnection(token);
       });
    } catch (error: any) {
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

        if (this.eventSource) {
            this.logger.warn('Closing pre-existing EventSource instance before reconnecting.');
            this.eventSource.close();
            this.removeMessageListeners();
        }

        this.eventSource = new EventSource(fullUrl);
        this.logger.info('EventSource instance created.');

        return new Promise<boolean>((resolve) => {
          this.eventSource!.onopen = () => {
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

          this.eventSource!.onerror = (errorEvent) => {
            this.logger.error('SSE onerror Event Triggered.', { readyState: this.eventSource?.readyState });

            if (this.eventSource?.readyState === EventSource.CLOSED) {
                 this.logger.warn('SSE onerror: Connection appears closed. Handling as disconnect.');
                 this.handleDisconnect('onerror_closed');
                 if (this.isConnecting) {
                     this.isConnecting = false;
                     this.emit('connection_failed', { error: 'SSE connection error during setup' });
                     resolve(false);
                 }
            } else if (this.eventSource?.readyState === EventSource.CONNECTING) {
                this.logger.warn('SSE onerror: Connection in connecting state (browser likely attempting internal retry).');
                const currentState = this.unifiedState.getServiceState(ConnectionServiceType.SSE).status;
                if (currentState === ConnectionStatus.CONNECTED) {
                     this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
                        status: ConnectionStatus.RECOVERING,
                        error: 'SSE connection interrupted, attempting recovery...'
                     });
                }
            } else {
                 this.logger.error('SSE onerror: Unknown state during error.', { errorEvent });
            }
          };

          this.setupMessageListeners();
        });
      } catch (error: any) {
        this.logger.error('SSE establishConnection caught synchronous error', { error: error.message });
        this.isConnecting = false;
        throw error;
      }
  }

  // Sets up listeners for named events from the SSE stream
  private setupMessageListeners(): void {
    if (!this.eventSource) return;
    this.logger.info('Setting up SSE message listeners.');

    this.eventSource.onmessage = (event: MessageEvent) => {
       this.logger.debug('SSE generic message received', { data: event.data });
        try {
            const parsedData = JSON.parse(event.data);
            this.emit('message', { type: 'message', data: parsedData });
        } catch (parseError: any) {
            this.logger.error('Failed to parse generic SSE message', { error: parseError.message, rawData: event.data });
            this.emit('error', { error: 'Failed to parse SSE message', originalError: parseError, rawData: event.data });
        }
    };

    this.eventSource.addEventListener('exchange-data', (event: MessageEvent) => {
       this.logger.debug('SSE exchange-data event received');
        try {
            const data = JSON.parse(event.data);
            this.emit('exchange-data', data);
            this.emit('message', { type: 'exchange-data', data });
        } catch (error: any) {
             this.logger.error('Failed to parse exchange-data event', { error: error.message, rawData: event.data });
             this.emit('error', { error: 'Failed to parse exchange-data event', originalError: error, rawData: event.data });
        }
    });

     this.eventSource.addEventListener('order-update', (event: MessageEvent) => {
       this.logger.debug('SSE order-update event received');
        try {
            const data = JSON.parse(event.data);
            this.emit('order-update', data);
            this.emit('message', { type: 'order-update', data });
        } catch (error: any) {
             this.logger.error('Failed to parse order-update event', { error: error.message, rawData: event.data });
             this.emit('error', { error: 'Failed to parse order-update event', originalError: error, rawData: event.data });
        }
    });

    this.eventSource.addEventListener('error-event', (event: MessageEvent) => {
       this.logger.error('SSE server-sent error event received', { data: event.data });
        try {
            const errorData = JSON.parse(event.data);
            this.emit('server_error', errorData);
            this.emit('error', { type: 'server_error', data: errorData });
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
       this.eventSource.onerror = null;
       this.eventSource.onopen = null;
       const dummyHandler = () => {};
       this.eventSource.removeEventListener('exchange-data', dummyHandler);
       this.eventSource.removeEventListener('order-update', dummyHandler);
       this.eventSource.removeEventListener('error-event', dummyHandler);
  }

  // Handles connection failures, logging and notifying via ErrorHandler
  private handleConnectionFailure(errorMessage: string) {
    this.logger.error(`SSE Connection Failure: ${errorMessage}`);
     this.isConnecting = false;

    this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
      status: ConnectionStatus.DISCONNECTED,
      error: `Connection failure: ${errorMessage}`
    });

    this.emit('connection_failed', { error: errorMessage });

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
    this.logger.warn(`SSE Disconnected. Reason: ${reason}`);
     this.isConnecting = false;

    const shouldAttemptReconnect = reason !== 'websocket_disconnected' && reason !== 'manual_close';
    const isWebSocketConnected = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status === ConnectionStatus.CONNECTED;
    const circuitIsOpen = this.circuitBreaker.getState() === CircuitState.OPEN;
    // *** Check authentication status BEFORE deciding to reconnect ***
    const isAuthenticated = this.tokenManager.isAuthenticated();

     const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
     if (sseState.status !== ConnectionStatus.DISCONNECTED) {
         this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
           status: ConnectionStatus.DISCONNECTED,
           error: `Connection lost (${reason})`
         });
          this.emit('disconnected', { reason });
     }

    // Attempt to reconnect if appropriate conditions are met
    if (shouldAttemptReconnect && isWebSocketConnected && isAuthenticated && !circuitIsOpen) { // <-- Added isAuthenticated check
      this.logger.info('Attempting SSE reconnect after disconnect.');
      this.attemptReconnect();
    } else {
       this.logger.warn('Not attempting SSE reconnect.', {
           shouldAttemptReconnect,
           isWebSocketConnected,
           isAuthenticated, // Log auth status
           circuitIsOpen,
           reason
       });
       if (!isAuthenticated) {
           // Reset counters because the disconnect is due to auth state
           this.reconnectAttempt = 0;
           this.backoffStrategy.reset();
       } else if (isWebSocketConnected) {
           this.errorHandler.handleConnectionError(
             `SSE Stream connection lost permanently. Circuit breaker may be open or max attempts reached. Reason: ${reason}`,
             ErrorSeverity.MEDIUM,
             'Data Stream (SSE)'
           );
           this.emit('connection_lost_permanently', { reason });
       }
    }
  }

  // Manages the reconnection attempt scheduling and execution
  private attemptReconnect(): void {
    if (this.reconnectTimer !== null) {
      this.logger.warn('SSE reconnect attempt skipped: Timer already active.');
      return;
    }

    // +++ ADDED AUTHENTICATION CHECK +++
    if (!this.tokenManager.isAuthenticated()) {
        this.logger.error('SSE reconnect attempt cancelled: User is not authenticated.');
        this.unifiedState.updateRecovery(false, this.reconnectAttempt); // Ensure recovery UI is hidden
        // Reset counters as user is logged out
        this.reconnectAttempt = 0;
        this.backoffStrategy.reset();
        return;
    }
    // +++ END CHECK +++

    // Pre-checks before scheduling
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
      return;
    }

    // Schedule the reconnect attempt
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
      this.logger.info(`Executing scheduled SSE reconnect attempt ${this.reconnectAttempt}.`);
      const connected = await this.connect();
      if (!connected) {
        this.logger.warn(`SSE reconnect attempt ${this.reconnectAttempt} failed.`);
      } else {
         this.logger.info(`SSE reconnect attempt ${this.reconnectAttempt} successful.`);
      }
    }, delay);

    this.errorHandler.handleConnectionError(
      `Reconnecting to data stream (Attempt ${this.reconnectAttempt})...`,
      ErrorSeverity.LOW,
      'Data Stream (SSE)'
    );
  }

  // Closes the SSE connection and stops any reconnection attempts
  public close(reason: string = 'manual_close'): void {
     this.logger.info(`SSE close requested. Reason: ${reason}`);
    this.stopReconnectTimer();

    if (this.eventSource) {
       this.logger.info('Closing existing EventSource.');
       this.removeMessageListeners();
       this.eventSource.onerror = null;
       this.eventSource.onopen = null;
       this.eventSource.onmessage = null;
       this.eventSource.close();
       this.eventSource = null;
    }
     this.isConnecting = false;

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
     this.reconnectAttempt = 0;
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
    const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
    return {
      connected: sseState.status === ConnectionStatus.CONNECTED,
      connecting: sseState.status === ConnectionStatus.CONNECTING,
      circuitBreakerState: this.circuitBreaker.getState(),
      reconnectAttempt: this.reconnectAttempt,
      maxReconnectAttempts: this.maxReconnectAttempts
    };
  }

  // Cleans up resources when the SSEManager is no longer needed
  public dispose(): void {
     this.logger.warn('Disposing SSEManager.');
    this.unifiedState.off('websocket_state_change', this.handleWebSocketStateChange.bind(this));
    this.close('dispose');
    this.removeAllListeners();
  }
}
