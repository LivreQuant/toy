// src/services/websocket/websocket-manager.ts

import { config } from '../../config';
import { EventEmitter } from '../../utils/event-emitter';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { CircuitBreaker, CircuitState } from '../../utils/circuit-breaker';
import { TokenManager } from '../auth/token-manager';
import { ConnectionStrategyDependencies } from './types';
import { ConnectionStrategy } from './connection-strategy';
import { HeartbeatManager } from './heartbeat-manager';
import {
  WebSocketErrorHandler,
  WebSocketError,
  NetworkError,
  AuthenticationError,
} from './websocket-error';
import { ErrorHandler as UtilsErrorHandler, ErrorSeverity } from '../../utils/error-handler';
import { WebSocketMessageHandler } from './message-handler';
import { DeviceIdManager } from '../../utils/device-id-manager';
import { Logger } from '../../utils/logger';
import {
  WebSocketOptions,
  ConnectionQuality as WSConnectionQuality,
  HeartbeatData,
  HeartbeatManagerDependencies,
} from './types';
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus,
  ConnectionQuality,
} from '../connection/unified-connection-state';
import { Disposable } from '../../utils/disposable';
import { toastService } from '../notification/toast-service';

// Define default values for resilience strategies
const DEFAULT_BACKOFF_INITIAL_MS = 1000; // 1 second
const DEFAULT_BACKOFF_MAX_MS = 30000; // 30 seconds
const DEFAULT_CB_FAILURE_THRESHOLD = 5;
const DEFAULT_CB_RESET_TIMEOUT_MS = 60000; // 1 minute
const DEFAULT_CB_MAX_HALF_OPEN_CALLS = 1;
const DEFAULT_RECONNECT_MAX_ATTEMPTS = 10;
const DEFAULT_HEARTBEAT_INTERVAL = 15000; // 15 seconds
const DEFAULT_HEARTBEAT_TIMEOUT = 5000; // 5 seconds


export class WebSocketManager extends EventEmitter implements Disposable {
  // --- Core Dependencies ---
  private tokenManager: TokenManager;
  private unifiedState: UnifiedConnectionState;
  private logger: Logger;
  private errorHandler: UtilsErrorHandler; // Use the injected generic error handler

  // --- Sub-Managers and Strategies ---
  private connectionStrategy: ConnectionStrategy;
  private heartbeatManager: HeartbeatManager | null = null;
  private messageHandler: WebSocketMessageHandler;
  private backoffStrategy: BackoffStrategy;
  private circuitBreaker: CircuitBreaker;
  // private metricTracker: MetricTracker; // Uncomment if used

  // --- State and Timers ---
  private reconnectTimer: number | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number;
  private isDisposed: boolean = false;
  private currentConnectionQuality: WSConnectionQuality = WSConnectionQuality.DISCONNECTED; // Internal WS quality

  // --- Options ---
  private wsOptions: WebSocketOptions;


  constructor(
    tokenManager: TokenManager,
    unifiedState: UnifiedConnectionState,
    logger: Logger,
    options: WebSocketOptions = {} // Accept options
  ) {
    super();
    this.tokenManager = tokenManager;
    this.unifiedState = unifiedState;
    this.logger = logger.createChild('WebSocketManager'); // Create child logger
    this.logger.info('WebSocketManager Initializing...');

    // Store merged options
    this.wsOptions = {
        heartbeatInterval: options.heartbeatInterval ?? DEFAULT_HEARTBEAT_INTERVAL,
        heartbeatTimeout: options.heartbeatTimeout ?? DEFAULT_HEARTBEAT_TIMEOUT,
        reconnectMaxAttempts: options.reconnectMaxAttempts ?? DEFAULT_RECONNECT_MAX_ATTEMPTS,
        // Add circuit breaker/backoff options if they should be configurable
    };
    this.maxReconnectAttempts = this.wsOptions.reconnectMaxAttempts!; // Use configured value

    // --- Instantiate Dependencies ---
    // Instantiate the generic ErrorHandler (verify dependencies)
    this.errorHandler = new UtilsErrorHandler(this.logger, toastService);

    // Instantiate resilience strategies with defaults or configured values
    this.backoffStrategy = new BackoffStrategy(
        DEFAULT_BACKOFF_INITIAL_MS,
        DEFAULT_BACKOFF_MAX_MS
    );
    this.circuitBreaker = new CircuitBreaker(
        'websocket-connection',
        DEFAULT_CB_FAILURE_THRESHOLD,
        DEFAULT_CB_RESET_TIMEOUT_MS,
        DEFAULT_CB_MAX_HALF_OPEN_CALLS
    );
    this.circuitBreaker.onStateChange(this.handleCircuitBreakerStateChange.bind(this));


    // Instantiate sub-managers
    // this.metricTracker = new MetricTracker(this.logger); // Uncomment if used

    // Ensure DeviceIdManager is initialized (it's a singleton, needs initialization once)
    const deviceIdManager = DeviceIdManager.getInstance(); // Get instance (must be initialized prior)

    const strategyDeps: ConnectionStrategyDependencies = {
      tokenManager,
      deviceIdManager, // Pass the singleton instance
      eventEmitter: this,
      logger: this.logger,
      options: this.wsOptions // Pass relevant options
    };
    this.connectionStrategy = new ConnectionStrategy(strategyDeps);

    // Pass logger to MessageHandler
    this.messageHandler = new WebSocketMessageHandler(this, this.logger);


    // --- Setup Event Listeners ---
    this.setupListeners();
    this.logger.info('WebSocketManager Initialized.');
  }

  /**
   * Sets up internal event listeners for connection, errors, heartbeats, etc.
   */
  private setupListeners(): void {
    this.logger.info('Setting up WebSocketManager listeners...');

    // Listen to events emitted by ConnectionStrategy
    this.on('ws_connected_internal', this.handleWsConnected.bind(this));
    this.on('ws_disconnected_internal', this.handleDisconnectEvent.bind(this));
    this.on('ws_error_internal', (errorData: any) => {
      if (this.isDisposed) return;
      const wsError = new WebSocketError(errorData.message || 'Connection strategy error', 'CONNECTION_STRATEGY_ERROR');
      // Route to generic error handler
      this.handleGenericError(wsError, ErrorSeverity.HIGH, 'WebSocket Internal');
    });

    // Listen to events emitted by MessageHandler
    this.messageHandler.on('message', this.handleIncomingMessage.bind(this));
    this.messageHandler.on('heartbeat', this.handleHeartbeatEvent.bind(this));
    this.messageHandler.on('session_invalidated', this.handleSessionInvalidated.bind(this));
    this.messageHandler.on('message_error', (errorInfo: { error: Error, rawData: string }) => {
        if (this.isDisposed) return;
        this.logger.error('Message handler reported an error.', errorInfo);
        this.handleGenericError(errorInfo.error, ErrorSeverity.MEDIUM, 'MessageHandler');
    });
    this.messageHandler.on('unknown_message', (message: any) => {
        if (this.isDisposed) return;
        this.logger.warn('Received message of unknown type from handler.', { type: message?.type });
    });

    // Listen for heartbeat timeout events
    this.on('heartbeat_timeout', this.handleHeartbeatTimeout.bind(this));
  }

  // --- Connection Lifecycle ---

  /**
   * Establishes the WebSocket connection using the ConnectionStrategy and CircuitBreaker.
   * Updates the UnifiedConnectionState.
   * @returns True if connection attempt is successful, false otherwise.
   */
  public async connect(): Promise<boolean> {
    if (this.isDisposed) {
        this.logger.error("Cannot connect: WebSocketManager is disposed.");
        return false;
    }
    const currentState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status;
    if (currentState === ConnectionStatus.CONNECTED || currentState === ConnectionStatus.CONNECTING) {
        this.logger.warn(`Connect call ignored: Already ${currentState}.`);
        return currentState === ConnectionStatus.CONNECTED;
    }

    this.logger.info("WebSocket connect requested.");
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        status: ConnectionStatus.CONNECTING,
        error: null,
        recoveryAttempts: this.reconnectAttempts
    });

    try {
      // Execute the connection attempt through the circuit breaker
      const ws = await this.circuitBreaker.execute(async () => {
        // The actual connection logic is inside ConnectionStrategy
        // ConnectionStrategy already checks for token before creating WebSocket
        return this.connectionStrategy.connect();
      });

      this.logger.info("WebSocket connection established successfully via Circuit Breaker.");
      // Note: handleWsConnected will be called via the 'ws_connected_internal' event

      // Reset failure counters on successful connection through circuit breaker
      this.reconnectAttempts = 0;
      this.backoffStrategy.reset();

      return true;

    } catch (error: any) {
      this.logger.error(`WebSocket connection failed. Reason: ${error.message}`, { name: error.name });
      this.handleGenericError(error, ErrorSeverity.HIGH, 'WebSocket Connect');
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.DISCONNECTED,
          error: error.message || 'Connection failed'
      });
      this.handleDisconnectEvent({ code: 0, reason: error.message, wasClean: false }); // Simulate disconnect event on failure
      return false;
    }
  }

  /**
   * Disconnects the WebSocket connection intentionally.
   * Updates UnifiedConnectionState and cleans up resources.
   * @param reason - A string indicating the reason for disconnection.
   */
  public disconnect(reason: string = 'Client disconnected'): void {
    if (this.isDisposed) return;
    this.logger.warn(`WebSocket disconnect requested. Reason: ${reason}`);

    this.stopReconnectTimer();
    this.heartbeatManager?.stop();
    this.heartbeatManager = null;

    this.connectionStrategy.disconnect();

    const currentState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    if (currentState.status !== ConnectionStatus.DISCONNECTED) {
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        status: ConnectionStatus.DISCONNECTED,
        error: reason,
        lastConnected: currentState.lastConnected
      });
    }

    if (reason === 'user_disconnect' || reason === 'logout' || reason === 'manager_disposed' || reason.startsWith('auth_')) {
        this.logger.info('Resetting backoff and circuit breaker due to clean/auth disconnect.');
        this.reconnectAttempts = 0;
        this.backoffStrategy.reset();
        this.circuitBreaker.reset();
        this.unifiedState.updateRecovery(false, 0);
    }
  }

  /**
   * Cleans up all resources used by the WebSocketManager.
   */
  public dispose(): void {
    if (this.isDisposed) return;
    this.logger.warn("Disposing WebSocketManager...");
    this.isDisposed = true;

    this.disconnect('manager_disposed');

    this.messageHandler?.removeAllListeners();
    this.removeAllListeners();

    this.logger.warn("WebSocketManager disposed.");
  }

  // --- Event Handlers ---

  /**
   * Handles the successful opening of the WebSocket connection.
   */
  private handleWsConnected(): void {
      if (this.isDisposed) return;
      this.logger.info('Internal WebSocket Connected event received.');

      const ws = this.connectionStrategy.getWebSocket();
      if (!ws) {
          this.logger.error("handleWsConnected called but WebSocket instance is null in strategy.");
          this.disconnect("internal_error_null_ws");
          return;
      }

      ws.onmessage = this.messageHandler.handleMessage.bind(this.messageHandler);
      ws.onerror = this.handleWebSocketErrorEvent.bind(this);

      const heartbeatDeps: HeartbeatManagerDependencies = {
          ws: ws,
          eventEmitter: this,
          options: {
              interval: this.wsOptions.heartbeatInterval,
              timeout: this.wsOptions.heartbeatTimeout
          }
      };
      this.heartbeatManager = new HeartbeatManager(heartbeatDeps);
      this.heartbeatManager.start();
      this.logger.info(`Heartbeat manager started with interval ${this.wsOptions.heartbeatInterval}ms, timeout ${this.wsOptions.heartbeatTimeout}ms.`);

      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.CONNECTED,
          lastConnected: Date.now(),
          error: null,
          recoveryAttempts: 0
      });
      this.unifiedState.updateRecovery(false, 0);

      this.reconnectAttempts = 0;
      this.backoffStrategy.reset();

      this.logger.info("WebSocket Manager setup complete after connection.");
  }

  /**
   * Handles the disconnection of the WebSocket.
   * @param details - Information about the disconnection event.
   */
  private handleDisconnectEvent(details: { code: number; reason: string; wasClean: boolean }): void {
    if (this.isDisposed) return;
    this.logger.warn(`Internal WebSocket Disconnected event received. Code: ${details.code}, Reason: "${details.reason}", Clean: ${details.wasClean}`);

    const ws = this.connectionStrategy.getWebSocket();
    if (ws) {
        ws.onmessage = null;
        ws.onerror = null;
    }
    this.heartbeatManager?.stop();
    this.heartbeatManager = null;

    const currentStatus = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status;
    if (currentStatus !== ConnectionStatus.DISCONNECTED) {
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
            status: ConnectionStatus.DISCONNECTED,
            error: details.reason || `WebSocket closed (Code: ${details.code})`,
        });
    }

    const isNormalClosure = details.code === 1000;
    // Consider auth errors (like 4001 or specific reasons) as non-recoverable automatically
    const isAuthRelatedClosure = details.code === 4001 || details.reason?.toLowerCase().includes('unauthorized') || details.reason?.toLowerCase().includes('invalid token');
    const circuitIsOpen = this.circuitBreaker.getState() === CircuitState.OPEN;
    const maxAttemptsReached = this.reconnectAttempts >= this.maxReconnectAttempts;

    // *** Check authentication status BEFORE deciding to reconnect ***
    const isAuthenticated = this.tokenManager.isAuthenticated();

    const shouldAttemptReconnect = !isNormalClosure && !isAuthRelatedClosure && isAuthenticated && !circuitIsOpen && !maxAttemptsReached;

    this.logger.info(`Should attempt reconnect? ${shouldAttemptReconnect}`, {
        isNormalClosure, isAuthRelatedClosure, isAuthenticated, circuitIsOpen, maxAttemptsReached, code: details.code
    });

    if (shouldAttemptReconnect) {
      this.attemptReconnect();
    } else {
      if (!isAuthenticated) {
          this.logger.warn("Not attempting reconnect: User is not authenticated.");
          // Reset counters because the disconnect is due to auth state
          this.reconnectAttempts = 0;
          this.backoffStrategy.reset();
          this.circuitBreaker.reset(); // Reset circuit breaker on auth issues
          this.unifiedState.updateRecovery(false, 0);
      } else if (isNormalClosure || isAuthRelatedClosure) {
         this.logger.info('Resetting reconnect attempts and backoff due to controlled/auth disconnect.');
         this.reconnectAttempts = 0;
         this.backoffStrategy.reset();
         if (isAuthRelatedClosure) this.circuitBreaker.reset();
         this.unifiedState.updateRecovery(false, 0);
      } else if (circuitIsOpen) {
           this.logger.warn("Not attempting reconnect: Circuit breaker is OPEN.");
           this.errorHandler.handleConnectionError(
               `WebSocket disconnected and circuit breaker is OPEN. Connection attempts suspended. Reason: ${details.reason}`,
               ErrorSeverity.HIGH,
               'WebSocket Disconnect'
           );
           this.unifiedState.updateRecovery(false, this.reconnectAttempts);
       } else if (maxAttemptsReached) {
            this.logger.error(`Not attempting reconnect: Max reconnect attempts (${this.maxReconnectAttempts}) reached.`);
            this.errorHandler.handleConnectionError(
               `Failed to reconnect WebSocket after ${this.maxReconnectAttempts} attempts. Giving up. Reason: ${details.reason}`,
               ErrorSeverity.HIGH,
               'WebSocket Disconnect'
           );
           this.unifiedState.updateRecovery(false, this.reconnectAttempts);
       }
    }
  }

   /**
    * Handles WebSocket 'error' events that occur *after* the connection is established.
    */
   private handleWebSocketErrorEvent(event: Event): void {
        if (this.isDisposed) return;
        this.logger.error('WebSocket runtime error event occurred.', { event });
        this.handleGenericError(new Error('WebSocket runtime error'), ErrorSeverity.MEDIUM, 'WebSocket Runtime');
   }

  /**
   * Handles incoming messages forwarded by the MessageHandler.
   */
  private handleIncomingMessage(message: any): void {
    if (this.isDisposed) return;
    // Optional: Log all incoming messages at debug level if needed
  }

  /**
   * Handles heartbeat responses received from the server (via MessageHandler).
   */
  private handleHeartbeatEvent(data: HeartbeatData): void {
    if (this.isDisposed) return;
    this.heartbeatManager?.handleHeartbeatResponse();

    const now = Date.now();
    const latency = data.timestamp ? (now - data.timestamp) : -1;
    this.unifiedState.updateHeartbeat(now, latency);

    if (data.simulatorStatus) {
      this.unifiedState.updateSimulatorStatus(data.simulatorStatus);
    }

    this.updateWsConnectionQuality(latency);
  }

  /**
   * Handles heartbeat timeout events emitted by the HeartbeatManager.
   */
  private handleHeartbeatTimeout(): void {
    if (this.isDisposed) return;
    this.logger.error('Heartbeat timeout detected.');
    const error = new WebSocketError('Connection lost (heartbeat timeout).', 'HEARTBEAT_TIMEOUT');
    this.handleGenericError(error, ErrorSeverity.HIGH, 'Heartbeat');
    this.connectionStrategy.disconnect(); // Force disconnect
  }

  /**
   * Handles session invalidation messages from the server (via MessageHandler).
   */
  private handleSessionInvalidated(details: { reason: string }): void {
    if (this.isDisposed) return;
    this.logger.error(`Session invalidated by server. Reason: ${details.reason}`);
    const error = new AuthenticationError(`Session invalidated: ${details.reason}. Please log in again.`);
    this.handleGenericError(error, ErrorSeverity.HIGH, 'SessionInvalidated');
    this.disconnect(`auth_session_invalidated: ${details.reason}`); // Use specific reason prefix
    this.triggerLogout(`session_invalidated: ${details.reason}`);
  }

   /**
    * Handles changes in the Circuit Breaker's state.
    */
   private handleCircuitBreakerStateChange(name: string, oldState: CircuitState, newState: CircuitState, info: any): void {
        if (this.isDisposed) return;
        this.logger.warn(`Circuit Breaker [${name}] state changed: ${oldState} -> ${newState}`, info);

        if (newState === CircuitState.OPEN) {
             this.errorHandler.handleConnectionError(
                'Multiple WebSocket connection failures detected. Connection attempts temporarily suspended.',
                ErrorSeverity.HIGH,
                'WebSocket CircuitBreaker'
             );
             this.unifiedState.updateRecovery(false, this.reconnectAttempts);
             this.emit('circuit_open', {
                message: 'WebSocket Connection attempts temporarily suspended due to repeated failures.',
                resetTimeoutMs: this.circuitBreaker.getResetTimeout()
             });
        } else if (newState === CircuitState.CLOSED) {
             this.emit('circuit_closed', { message: 'WebSocket Circuit breaker closed. Connections re-enabled.' });
             const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
             // *** Check authentication before attempting reconnect after circuit closed ***
             if (wsState.status === ConnectionStatus.DISCONNECTED && this.tokenManager.isAuthenticated()) {
                 this.logger.info('Circuit breaker closed, attempting reconnect...');
                 this.attemptReconnect();
             } else if (!this.tokenManager.isAuthenticated()) {
                  this.logger.info('Circuit breaker closed, but user not authenticated. Skipping reconnect.');
             }
        }
   }

  /**
   * Central routing point for handling errors within WebSocketManager.
   */
  private handleGenericError(
    error: Error | string,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    context: string = 'WebSocket'
  ): void {
    if (this.isDisposed) return;
    this.logger.error(`[${context}] Handling error:`, { error, severity });

    if (error instanceof AuthenticationError) {
      this.errorHandler.handleAuthError(error, severity, context);
    } else if (error instanceof NetworkError || error instanceof WebSocketError || (typeof error === 'string' && error.includes('Connection'))) {
      this.errorHandler.handleConnectionError(error, severity, context);
    } else if (error instanceof Error && error.message.includes('Data')) {
       this.errorHandler.handleDataError(error, severity, context);
    }
    else {
      this.errorHandler.handleGenericError(error, severity, context);
    }

    const errorMessage = typeof error === 'string' ? error : error.message;
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        error: errorMessage
    });
  }

  // --- Reconnection Logic ---

  /**
   * Stops any active reconnection timer.
   */
  private stopReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      this.logger.info('Stopping WebSocket reconnect timer.');
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * Attempts to reconnect the WebSocket connection after a delay.
   * Respects backoff strategy, max attempts, circuit breaker state, and authentication status.
   */
  private attemptReconnect(): void {
    if (this.isDisposed || this.reconnectTimer !== null) {
        if (this.reconnectTimer !== null) this.logger.warn('Reconnect attempt skipped: Timer already active.');
        return; // Already trying or disposed
    }

    // +++ ADDED AUTHENTICATION CHECK +++
    if (!this.tokenManager.isAuthenticated()) {
        this.logger.error('Reconnect attempt cancelled: User is not authenticated.');
        this.unifiedState.updateRecovery(false, this.reconnectAttempts); // Ensure recovery UI is hidden
        // Reset counters as user is logged out
        this.reconnectAttempts = 0;
        this.backoffStrategy.reset();
        return;
    }
    // +++ END CHECK +++

    // --- Pre-checks ---
    if (this.circuitBreaker.getState() === CircuitState.OPEN) {
      this.logger.error('Reconnect attempt cancelled: Circuit breaker is OPEN.');
      return;
    }
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.logger.error(`Reconnect attempt cancelled: Max attempts (${this.maxReconnectAttempts}) reached.`);
      return;
    }

    // --- Schedule Reconnect ---
    this.reconnectAttempts++;
    const delay = this.backoffStrategy.nextBackoffTime();
    this.logger.info(`Scheduling WebSocket reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms.`);

    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        status: ConnectionStatus.RECOVERING,
        error: `Reconnecting (attempt ${this.reconnectAttempts})...`,
        recoveryAttempts: this.reconnectAttempts
    });
    this.unifiedState.updateRecovery(true, this.reconnectAttempts);

    this.emit('reconnecting', {
        attempt: this.reconnectAttempts,
        maxAttempts: this.maxReconnectAttempts,
        delay
    });

    this.errorHandler.handleConnectionError(
        `Attempting to reconnect WebSocket (Attempt ${this.reconnectAttempts})...`,
        ErrorSeverity.LOW,
        'WebSocket Reconnect'
    );

    this.reconnectTimer = window.setTimeout(async () => {
      this.reconnectTimer = null;
      this.logger.info(`Executing scheduled WebSocket reconnect attempt ${this.reconnectAttempts}.`);
      // connect() handles circuit breaker checks, state updates, and further errors
      const connected = await this.connect();
      if (!connected) {
        this.logger.warn(`WebSocket reconnect attempt ${this.reconnectAttempts} failed.`);
        // Failure handling (including potential next attempt) is managed by connect() -> handleDisconnectEvent()
      } else {
         this.logger.info(`WebSocket reconnect attempt ${this.reconnectAttempts} successful.`);
         // Success handling (resetting attempts etc.) is done within connect() / handleWsConnected()
      }
    }, delay);
  }

  /**
   * Initiates a manual reconnection attempt immediately.
   * Resets backoff, circuit breaker, and attempt counters.
   */
  public manualReconnect(): void {
    if (this.isDisposed) {
        this.logger.error("Manual reconnect ignored: WebSocketManager disposed.");
        return;
    }
    this.logger.warn('Manual reconnect requested.');

    // *** Add auth check for manual reconnect ***
    if (!this.tokenManager.isAuthenticated()) {
        this.logger.error('Manual reconnect failed: User is not authenticated.');
        this.errorHandler.handleAuthError("Cannot reconnect: Please log in first.", ErrorSeverity.MEDIUM, "ManualReconnect");
        return;
    }

    this.stopReconnectTimer();
    this.reconnectAttempts = 0;
    this.backoffStrategy.reset();
    this.circuitBreaker.reset();

    this.unifiedState.updateRecovery(true, 1);

    this.connect();
  }

  // --- Utility Methods ---

  /**
   * Sends a message through the WebSocket connection.
   * @param message - The message object to send (will be JSON.stringify'd).
   * @throws {Error} If the WebSocket is not open or the manager is disposed.
   */
  public send(message: any): void {
    if (this.isDisposed) throw new Error("WebSocketManager is disposed.");

    const ws = this.connectionStrategy.getWebSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify(message));
      } catch (error: any) {
         this.logger.error('Failed to send WebSocket message', { error: error.message, messageType: message?.type });
         throw new Error(`Failed to send WebSocket message: ${error.message}`);
      }
    } else {
      this.logger.error('Cannot send message: WebSocket is not open.', { readyState: ws?.readyState });
      throw new Error('WebSocket connection is not open.');
    }
  }

  /**
   * Triggers the logout process by clearing tokens and notifying the application.
   * @param reason - The reason for triggering logout.
   */
  private triggerLogout(reason: string = 'unknown'): void {
    if (this.isDisposed) return;
    this.logger.warn(`Triggering logout process. Reason: ${reason}`);

    this.disconnect(`logout: ${reason}`);
    this.tokenManager.clearTokens();
    this.errorHandler.handleAuthError('Session ended. Please log in again.', ErrorSeverity.HIGH, 'LogoutTrigger');
    this.emit('force_logout', { reason });
  }


  /**
   * Updates the internal WebSocket connection quality metric based on latency.
   */
  private updateWsConnectionQuality(latency: number): void {
    if (this.isDisposed) return;
    const newQuality = this.calculateWsConnectionQuality(latency);
    if (newQuality !== this.currentConnectionQuality) {
      this.logger.info(`Internal WebSocket connection quality changed: ${this.currentConnectionQuality} -> ${newQuality} (Latency: ${latency}ms)`);
      this.currentConnectionQuality = newQuality;
    }
  }

  /**
   * Calculates the internal WebSocket quality level based on latency.
   */
  private calculateWsConnectionQuality(latency: number): WSConnectionQuality {
    if (latency < 0) return WSConnectionQuality.DISCONNECTED;
    if (latency <= 150) return WSConnectionQuality.EXCELLENT;
    if (latency <= 500) return WSConnectionQuality.GOOD;
    if (latency <= 1000) return WSConnectionQuality.FAIR;
    return WSConnectionQuality.POOR;
  }

  /**
   * Gets the current health status of the WebSocket connection.
   */
  public getConnectionHealth() {
    if (this.isDisposed) return { status: 'disconnected', quality: WSConnectionQuality.DISCONNECTED, error: 'Manager disposed' };

    const serviceState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    let statusString: 'connected' | 'connecting' | 'recovering' | 'disconnected';

    switch (serviceState.status) {
      case ConnectionStatus.CONNECTED: statusString = 'connected'; break;
      case ConnectionStatus.CONNECTING: statusString = 'connecting'; break;
      case ConnectionStatus.RECOVERING: statusString = 'recovering'; break;
      case ConnectionStatus.DISCONNECTED: default: statusString = 'disconnected'; break;
    }

    return {
      status: statusString,
      quality: this.currentConnectionQuality,
      error: serviceState.error
    };
  }

  /**
   * Checks if the WebSocket is currently in the process of connecting or recovering.
   */
  public isConnectingOrRecovering(): boolean {
    if (this.isDisposed) return false;
    const status = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status;
    return status === ConnectionStatus.CONNECTING || status === ConnectionStatus.RECOVERING;
  }

  /**
   * Implements the [Symbol.dispose] method for the Disposable interface.
   */
  [Symbol.dispose](): void {
    this.dispose();
  }
}
