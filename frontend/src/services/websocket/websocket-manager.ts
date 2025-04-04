// src/services/websocket/websocket-manager.ts

import { config } from '../../config';
import { EventEmitter } from '../../utils/event-emitter';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { CircuitBreaker, CircuitState } from '../../utils/circuit-breaker';
import { TokenManager } from '../auth/token-manager';
// *** FIX: Import ConnectionStrategyDependencies correctly ***
import { ConnectionStrategy, ConnectionStrategyDependencies } from './connection-strategy';
import { HeartbeatManager } from './heartbeat-manager';
import {
  WebSocketErrorHandler,
  WebSocketError,
  NetworkError,
  AuthenticationError,
} from './websocket-error';
// *** FIX: Import the correct ErrorHandler and ErrorSeverity from utils ***
import { ErrorHandler as UtilsErrorHandler, ErrorSeverity } from '../../utils/error-handler';
import { WebSocketMessageHandler } from './message-handler';
import { DeviceIdManager } from '../../utils/device-id-manager';
// *** FIX: Import MetricTracker from the correct path if needed, or remove if unused ***
// Assuming MetricTracker is in utils now based on previous context
// import { MetricTracker } from '../../utils/metric-tracker';
import { Logger } from '../../utils/logger';
import {
  WebSocketOptions,
  // ConnectionMetrics, // Likely unused directly here now
  ConnectionQuality as WSConnectionQuality, // Renamed to avoid conflict
  HeartbeatData,
  HeartbeatManagerDependencies, // Import this if needed for HeartbeatManager instantiation
} from './types'; // Ensure types.ts has necessary exports
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus,
  ConnectionQuality, // This might conflict, consider renaming if used alongside WSConnectionQuality
} from '../connection/unified-connection-state';
import { Disposable } from '../../utils/disposable';
// +++ ADDED: Import ToastService for ErrorHandler instantiation +++
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
    // +++ FIXED: Replaced placeholder args with defaults +++
    this.backoffStrategy = new BackoffStrategy(
        DEFAULT_BACKOFF_INITIAL_MS, // Use defaults or options.backoffInitialMs
        DEFAULT_BACKOFF_MAX_MS      // Use defaults or options.backoffMaxMs
    );
    // +++ FIXED: Replaced placeholder args with defaults +++
    this.circuitBreaker = new CircuitBreaker(
        'websocket-connection',             // Descriptive name
        DEFAULT_CB_FAILURE_THRESHOLD,       // Use defaults or options.cbFailureThreshold
        DEFAULT_CB_RESET_TIMEOUT_MS,        // Use defaults or options.cbResetTimeoutMs
        DEFAULT_CB_MAX_HALF_OPEN_CALLS      // Use defaults or options.cbMaxHalfOpenCalls
    );
    this.circuitBreaker.onStateChange(this.handleCircuitBreakerStateChange.bind(this));


    // Instantiate sub-managers
    // this.metricTracker = new MetricTracker(this.logger); // Uncomment if used

    // Ensure DeviceIdManager is initialized (it's a singleton, needs initialization once)
    // This might happen elsewhere, e.g., in ConnectionManager or app setup
    // DeviceIdManager.getInstance(storageService, logger); // Example initialization call
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
    this.messageHandler.on('message', this.handleIncomingMessage.bind(this)); // Listen for all messages if needed
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
        // Decide if this needs specific handling
    });
    // Add listeners for specific message types if WebSocketManager needs to react directly
    // this.messageHandler.on('order_update', (data: any) => { ... });

    // Listen to events emitted by HeartbeatManager (via MessageHandler's heartbeat event)
    // We also need a timeout mechanism if heartbeats stop coming back
    // HeartbeatManager itself handles sending and timeout detection internally now.
    // We listen for 'heartbeat_timeout' emitted by HeartbeatManager.
    // This event needs to be emitted by HeartbeatManager and potentially relayed
    // For simplicity, let's assume HeartbeatManager emits 'heartbeat_timeout' on `this` (the EventEmitter passed to it)
    this.on('heartbeat_timeout', this.handleHeartbeatTimeout.bind(this));


    // Listen for external force logout requests (e.g., from UI)
    // this.on('force_logout_request', (reason: string) => { ... });
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
        recoveryAttempts: this.reconnectAttempts // Reflect current attempt count
    });

    try {
      // Execute the connection attempt through the circuit breaker
      const ws = await this.circuitBreaker.execute(async () => {
        // The actual connection logic is inside ConnectionStrategy
        return this.connectionStrategy.connect();
      });

      // If circuit breaker allowed execution and strategy succeeded:
      this.logger.info("WebSocket connection established successfully via Circuit Breaker.");
      // Note: handleWsConnected will be called via the 'ws_connected_internal' event

      // Reset failure counters on successful connection through circuit breaker
      this.reconnectAttempts = 0;
      this.backoffStrategy.reset();
      // Circuit breaker resets automatically on success after HALF-OPEN

      return true;

    } catch (error: any) {
      // Handle errors from circuit breaker (OPEN state) or connectionStrategy.connect()
      this.logger.error(`WebSocket connection failed. Reason: ${error.message}`, { name: error.name });
      // Route the error for handling (logging, state update, potential reconnect)
      this.handleGenericError(error, ErrorSeverity.HIGH, 'WebSocket Connect');
      // Ensure state is marked as disconnected on failure
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.DISCONNECTED,
          error: error.message || 'Connection failed'
      });
      // Trigger reconnect logic if appropriate (handled by handleDisconnectEvent called by state update/error handling)
      this.handleDisconnectEvent({ code: 0, reason: error.message, wasClean: false }); // Simulate disconnect event on failure
      return false;
    }
  }

  /**
   * Disconnects the WebSocket connection intentionally.
   * Updates UnifiedConnectionState and cleans up resources.
   * @param reason - A string indicating the reason for disconnection.
   */
  public disconnect(reason: string = 'user_disconnect'): void {
    if (this.isDisposed) return;
    this.logger.warn(`WebSocket disconnect requested. Reason: ${reason}`);

    // Stop any pending reconnection attempts
    this.stopReconnectTimer();

    // Stop heartbeat mechanism
    this.heartbeatManager?.stop();
    this.heartbeatManager = null;

    // Disconnect the underlying strategy
    this.connectionStrategy.disconnect(); // This should trigger 'ws_disconnected_internal' if not already closed

    // Update unified state immediately if not already disconnected
    const currentState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    if (currentState.status !== ConnectionStatus.DISCONNECTED) {
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        status: ConnectionStatus.DISCONNECTED,
        error: reason,
        lastConnected: currentState.lastConnected // Preserve last connected time
      });
    }

    // Reset resilience mechanisms if it's a clean disconnect
    if (reason === 'user_disconnect' || reason === 'logout' || reason === 'manager_disposed') {
        this.logger.info('Resetting backoff and circuit breaker due to clean disconnect.');
        this.reconnectAttempts = 0;
        this.backoffStrategy.reset();
        this.circuitBreaker.reset(); // Manually reset circuit breaker on clean disconnect
        this.unifiedState.updateRecovery(false, 0); // Ensure recovery state is cleared
    }
  }

  /**
   * Cleans up all resources used by the WebSocketManager.
   */
  public dispose(): void {
    if (this.isDisposed) return;
    this.logger.warn("Disposing WebSocketManager...");
    this.isDisposed = true;

    this.disconnect('manager_disposed'); // Ensure cleanup via disconnect

    // Clean up message handler listeners
    this.messageHandler?.removeAllListeners();

    // Clean up own listeners
    this.removeAllListeners();

    // Nullify references
    // this.connectionStrategy = null; // Might not be necessary if disconnect handles it
    // this.messageHandler = null;
    // this.heartbeatManager = null;
    // ... other references ...

    this.logger.warn("WebSocketManager disposed.");
  }

  // --- Event Handlers ---

  /**
   * Handles the successful opening of the WebSocket connection.
   * Triggered by the 'ws_connected_internal' event from ConnectionStrategy.
   */
  private handleWsConnected(): void {
      if (this.isDisposed) return;
      this.logger.info('Internal WebSocket Connected event received.');

      const ws = this.connectionStrategy.getWebSocket();
      if (!ws) {
          this.logger.error("handleWsConnected called but WebSocket instance is null in strategy.");
          // Attempt to disconnect cleanly as state is inconsistent
          this.disconnect("internal_error_null_ws");
          return;
      }

      // --- Setup after connection ---
      // 1. Setup message listener on the actual WebSocket instance
      ws.onmessage = this.messageHandler.handleMessage.bind(this.messageHandler);
      ws.onerror = this.handleWebSocketErrorEvent.bind(this); // Handle runtime errors

      // 2. Start Heartbeat
      const heartbeatDeps: HeartbeatManagerDependencies = {
          ws: ws,
          eventEmitter: this, // HeartbeatManager will emit 'heartbeat_timeout' on this instance
          options: {
              interval: this.wsOptions.heartbeatInterval,
              timeout: this.wsOptions.heartbeatTimeout
          }
      };
      this.heartbeatManager = new HeartbeatManager(heartbeatDeps);
      this.heartbeatManager.start();
      this.logger.info(`Heartbeat manager started with interval ${this.wsOptions.heartbeatInterval}ms, timeout ${this.wsOptions.heartbeatTimeout}ms.`);

      // 3. Update Unified State
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.CONNECTED,
          lastConnected: Date.now(),
          error: null,
          recoveryAttempts: 0 // Reset recovery attempts on successful connect
      });
      this.unifiedState.updateRecovery(false, 0); // Ensure recovery overlay/state is cleared

      // 4. Reset resilience strategies (might be redundant if connect already did this)
      this.reconnectAttempts = 0;
      this.backoffStrategy.reset();
      // Circuit breaker resets on success automatically if it was HALF_OPEN

      this.logger.info("WebSocket Manager setup complete after connection.");
  }

  /**
   * Handles the disconnection of the WebSocket.
   * Triggered by the 'ws_disconnected_internal' event from ConnectionStrategy.
   * @param details - Information about the disconnection event.
   */
  private handleDisconnectEvent(details: { code: number; reason: string; wasClean: boolean }): void {
    if (this.isDisposed) return;
    this.logger.warn(`Internal WebSocket Disconnected event received. Code: ${details.code}, Reason: "${details.reason}", Clean: ${details.wasClean}`);

    // Clean up WebSocket specific listeners and heartbeat
    const ws = this.connectionStrategy.getWebSocket(); // Get WS before strategy nullifies it
    if (ws) {
        ws.onmessage = null;
        ws.onerror = null;
        // ws.onclose is handled by strategy
        // ws.onopen is handled by strategy
    }
    this.heartbeatManager?.stop();
    this.heartbeatManager = null;

    // Update unified state (ensure it reflects disconnected)
    const currentStatus = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status;
    if (currentStatus !== ConnectionStatus.DISCONNECTED) {
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
            status: ConnectionStatus.DISCONNECTED,
            error: details.reason || `WebSocket closed (Code: ${details.code})`,
            // Keep lastConnected time
        });
    }

    // Decide whether to attempt reconnection
    // Don't reconnect for clean closures (code 1000) or specific handled codes (like auth errors handled elsewhere)
    // Also respect circuit breaker state and max attempts
    const isNormalClosure = details.code === 1000;
    const isAuthRelatedClosure = details.code === 4001 || details.reason?.includes('unauthorized'); // Example custom codes/reasons
    const circuitIsOpen = this.circuitBreaker.getState() === CircuitState.OPEN;
    const maxAttemptsReached = this.reconnectAttempts >= this.maxReconnectAttempts;

    const shouldAttemptReconnect = !isNormalClosure && !isAuthRelatedClosure && !circuitIsOpen && !maxAttemptsReached;

    this.logger.info(`Should attempt reconnect? ${shouldAttemptReconnect}`, {
        isNormalClosure, isAuthRelatedClosure, circuitIsOpen, maxAttemptsReached, code: details.code
    });

    if (shouldAttemptReconnect) {
      this.attemptReconnect();
    } else {
      // If not reconnecting, ensure resilience mechanisms are reset if appropriate
      if (isNormalClosure || isAuthRelatedClosure) {
         this.logger.info('Resetting reconnect attempts and backoff due to controlled disconnect.');
         this.reconnectAttempts = 0;
         this.backoffStrategy.reset();
         // Optionally reset circuit breaker on auth errors if desired
         // if (isAuthRelatedClosure) this.circuitBreaker.reset();
      }
       if (circuitIsOpen) {
           this.logger.warn("Not attempting reconnect: Circuit breaker is OPEN.");
           this.errorHandler.handleConnectionError(
               `WebSocket disconnected and circuit breaker is OPEN. Connection attempts suspended. Reason: ${details.reason}`,
               ErrorSeverity.HIGH,
               'WebSocket Disconnect'
           );
       }
       if (maxAttemptsReached) {
            this.logger.error(`Not attempting reconnect: Max reconnect attempts (${this.maxReconnectAttempts}) reached.`);
            this.errorHandler.handleConnectionError(
               `Failed to reconnect WebSocket after ${this.maxReconnectAttempts} attempts. Giving up. Reason: ${details.reason}`,
               ErrorSeverity.HIGH,
               'WebSocket Disconnect'
           );
       }
       // Ensure recovery UI is hidden if we give up
       this.unifiedState.updateRecovery(false, this.reconnectAttempts);
    }
  }

   /**
    * Handles WebSocket 'error' events that occur *after* the connection is established.
    * These are often network-related issues that might precede a close event.
    * @param event - The WebSocket error event.
    */
   private handleWebSocketErrorEvent(event: Event): void {
        if (this.isDisposed) return;
        this.logger.error('WebSocket runtime error event occurred.', { event });
        // This event itself doesn't always mean disconnection, but often precedes it.
        // We can log it, but primary disconnect handling relies on the 'onclose' event.
        // Optionally, update state with a generic error, but it might be quickly overwritten by disconnect.
        // this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        //     error: 'WebSocket runtime error occurred'
        // });
        // Route to generic error handler for logging/notification
        this.handleGenericError(new Error('WebSocket runtime error'), ErrorSeverity.MEDIUM, 'WebSocket Runtime');
   }

  /**
   * Handles incoming messages forwarded by the MessageHandler.
   * @param message - The parsed message object.
   */
  private handleIncomingMessage(message: any): void {
    if (this.isDisposed) return;
    // Optional: Log all incoming messages at debug level if needed
    // this.logger.debug('WebSocketManager received message:', message);
    // Most message handling is done within MessageHandler and events are emitted.
    // This handler is a central point if WebSocketManager needs to react to *any* message.
  }

  /**
   * Handles heartbeat responses received from the server (via MessageHandler).
   * Updates connection quality and heartbeat state.
   * @param data - The heartbeat data from the server.
   */
  private handleHeartbeatEvent(data: HeartbeatData): void {
    if (this.isDisposed) return;
    // Notify the HeartbeatManager that a response was received (resets its internal timeout)
    this.heartbeatManager?.handleHeartbeatResponse();

    // Update unified state with heartbeat info
    const now = Date.now();
    // Calculate latency based on server timestamp if available
    const latency = data.timestamp ? (now - data.timestamp) : -1; // Use -1 if timestamp missing
    this.unifiedState.updateHeartbeat(now, latency);

    // Update simulator status if included in heartbeat
    if (data.simulatorStatus) {
      this.unifiedState.updateSimulatorStatus(data.simulatorStatus);
    }

    // Update internal WebSocket connection quality metric
    this.updateWsConnectionQuality(latency);
  }

  /**
   * Handles heartbeat timeout events emitted by the HeartbeatManager.
   */
  private handleHeartbeatTimeout(): void {
    if (this.isDisposed) return;
    this.logger.error('Heartbeat timeout detected.');

    // Create a specific error
    const error = new WebSocketError('Connection lost (heartbeat timeout).', 'HEARTBEAT_TIMEOUT');

    // Route the error for handling (logging, state update)
    this.handleGenericError(error, ErrorSeverity.HIGH, 'Heartbeat');

    // Force disconnection of the strategy, which will trigger handleDisconnectEvent
    this.connectionStrategy.disconnect('heartbeat_timeout');
  }

  /**
   * Handles session invalidation messages from the server (via MessageHandler).
   * This could be due to logout, inactivity, or another tab taking over.
   * @param details - Information about the invalidation.
   */
  private handleSessionInvalidated(details: { reason: string }): void {
    if (this.isDisposed) return;
    this.logger.error(`Session invalidated by server. Reason: ${details.reason}`);

    // Create an authentication error
    const error = new AuthenticationError(`Session invalidated: ${details.reason}. Please log in again.`);

    // Route the auth error - this should trigger logout via the ErrorHandler
    this.handleGenericError(error, ErrorSeverity.HIGH, 'SessionInvalidated');

    // Force disconnect with a specific reason
    this.disconnect(`session_invalidated: ${details.reason}`);

    // Explicitly trigger logout process (clear tokens, notify UI)
    this.triggerLogout(`session_invalidated: ${details.reason}`);
  }

   /**
    * Handles changes in the Circuit Breaker's state.
    */
   private handleCircuitBreakerStateChange(name: string, oldState: CircuitState, newState: CircuitState, info: any): void {
        if (this.isDisposed) return;
        this.logger.warn(`Circuit Breaker [${name}] state changed: ${oldState} -> ${newState}`, info);

        // Update unified state with circuit breaker status if needed
        // this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, { circuitBreakerState: newState });

        if (newState === CircuitState.OPEN) {
             this.errorHandler.handleConnectionError(
                'Multiple WebSocket connection failures detected. Connection attempts temporarily suspended.',
                ErrorSeverity.HIGH,
                'WebSocket CircuitBreaker'
             );
             // Ensure recovery UI reflects that attempts are suspended
             this.unifiedState.updateRecovery(false, this.reconnectAttempts); // Keep attempts count, but show not recovering
             this.emit('circuit_open', {
                message: 'WebSocket Connection attempts temporarily suspended due to repeated failures.',
                resetTimeoutMs: this.circuitBreaker.getResetTimeout() // Assuming getter exists
             });
        } else if (newState === CircuitState.CLOSED) {
             this.emit('circuit_closed', { message: 'WebSocket Circuit breaker closed. Connections re-enabled.' });
             // If state was disconnected, maybe trigger a reconnect attempt now that circuit is closed
             const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
             if (wsState.status === ConnectionStatus.DISCONNECTED) {
                 this.logger.info('Circuit breaker closed, attempting reconnect...');
                 this.attemptReconnect(); // Attempt reconnect now
             }
        }
   }

  /**
   * Central routing point for handling errors within WebSocketManager.
   * Uses the injected generic ErrorHandler.
   * @param error - The error object or message string.
   * @param severity - The severity level of the error.
   * @param context - A string providing context about where the error occurred.
   */
  private handleGenericError(
    error: Error | string,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    context: string = 'WebSocket'
  ): void {
    if (this.isDisposed) return;
    this.logger.error(`[${context}] Handling error:`, { error, severity });

    // Use the appropriate method on the injected ErrorHandler instance
    if (error instanceof AuthenticationError) {
      this.errorHandler.handleAuthError(error, severity, context);
    } else if (error instanceof NetworkError || error instanceof WebSocketError || (typeof error === 'string' && error.includes('Connection'))) {
      // Treat WebSocketErrors and NetworkErrors as connection errors for notification purposes
      this.errorHandler.handleConnectionError(error, severity, context);
    } else if (error instanceof Error && error.message.includes('Data')) { // Example check for data errors
       this.errorHandler.handleDataError(error, severity, context);
    }
    else {
      this.errorHandler.handleGenericError(error, severity, context);
    }

    // Update state with the error message
    const errorMessage = typeof error === 'string' ? error : error.message;
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        error: errorMessage
        // Avoid changing status here directly, let disconnect/connect logic handle status
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
   * Respects backoff strategy, max attempts, and circuit breaker state.
   */
  private attemptReconnect(): void {
    if (this.isDisposed || this.reconnectTimer !== null) {
        if (this.reconnectTimer !== null) this.logger.warn('Reconnect attempt skipped: Timer already active.');
        return; // Already trying or disposed
    }

    // --- Pre-checks ---
    if (this.circuitBreaker.getState() === CircuitState.OPEN) {
      this.logger.error('Reconnect attempt cancelled: Circuit breaker is OPEN.');
      // Error already logged/handled by circuit breaker state change handler
      return;
    }
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.logger.error(`Reconnect attempt cancelled: Max attempts (${this.maxReconnectAttempts}) reached.`);
      // Error already logged/handled by disconnect handler
      return;
    }

    // --- Schedule Reconnect ---
    this.reconnectAttempts++;
    const delay = this.backoffStrategy.nextBackoffTime();
    this.logger.info(`Scheduling WebSocket reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms.`);

    // Update unified state to show recovering status
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        status: ConnectionStatus.RECOVERING,
        error: `Reconnecting (attempt ${this.reconnectAttempts})...`,
        recoveryAttempts: this.reconnectAttempts
    });
    this.unifiedState.updateRecovery(true, this.reconnectAttempts); // Update overall recovery state

    // Emit event for UI feedback
    this.emit('reconnecting', {
        attempt: this.reconnectAttempts,
        maxAttempts: this.maxReconnectAttempts,
        delay
    });

    // Use ErrorHandler for low-severity notification
    this.errorHandler.handleConnectionError(
        `Attempting to reconnect WebSocket (Attempt ${this.reconnectAttempts})...`,
        ErrorSeverity.LOW,
        'WebSocket Reconnect'
    );


    // Set the timer
    this.reconnectTimer = window.setTimeout(async () => {
      this.reconnectTimer = null; // Clear timer ID before attempting connect
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

    // Stop any existing automatic reconnect timer
    this.stopReconnectTimer();

    // Reset resilience mechanisms fully for a manual attempt
    this.reconnectAttempts = 0;
    this.backoffStrategy.reset();
    this.circuitBreaker.reset(); // Force reset circuit breaker

    // Update state to show recovery initiated by user
    this.unifiedState.updateRecovery(true, 1); // Show recovery attempt 1

    // Initiate connection attempt
    this.connect(); // connect() will handle setting status to CONNECTING etc.
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
        // Optional: Log sent message at debug level
        // this.logger.debug('WebSocket message sent:', message);
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

    // Ensure connection is fully closed
    this.disconnect(`logout: ${reason}`);

    // Clear authentication tokens
    this.tokenManager.clearTokens();

    // Notify application using a generic, high-severity auth error
    // This assumes the ErrorHandler or UI listeners will handle the redirect/UI update
    this.errorHandler.handleAuthError('Session ended. Please log in again.', ErrorSeverity.HIGH, 'LogoutTrigger');

    // Emit a specific event that UI components can listen for to force redirect/cleanup
    this.emit('force_logout', { reason });
  }


  /**
   * Updates the internal WebSocket connection quality metric based on latency.
   * @param latency - The measured latency in milliseconds.
   */
  private updateWsConnectionQuality(latency: number): void {
    if (this.isDisposed) return;
    const newQuality = this.calculateWsConnectionQuality(latency);
    if (newQuality !== this.currentConnectionQuality) {
      this.logger.info(`Internal WebSocket connection quality changed: ${this.currentConnectionQuality} -> ${newQuality} (Latency: ${latency}ms)`);
      this.currentConnectionQuality = newQuality;
      // Emit specific event if needed for internal logic, but overall quality comes from UnifiedState
      // this.emit('internal_ws_quality_changed', this.currentConnectionQuality);
    }
  }

  /**
   * Calculates the internal WebSocket quality level based on latency.
   * @param latency - The measured latency in milliseconds.
   * @returns The calculated WSConnectionQuality.
   */
  private calculateWsConnectionQuality(latency: number): WSConnectionQuality {
    if (latency < 0) return WSConnectionQuality.DISCONNECTED; // Invalid latency
    if (latency <= 150) return WSConnectionQuality.EXCELLENT;
    if (latency <= 500) return WSConnectionQuality.GOOD;
    if (latency <= 1000) return WSConnectionQuality.FAIR;
    return WSConnectionQuality.POOR;
  }

  /**
   * Gets the current health status of the WebSocket connection.
   * Derives status primarily from UnifiedConnectionState.
   * @returns An object containing status, quality, and error information.
   */
  public getConnectionHealth() {
    if (this.isDisposed) return { status: 'disconnected', quality: WSConnectionQuality.DISCONNECTED, error: 'Manager disposed' };

    const serviceState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    let statusString: 'connected' | 'connecting' | 'recovering' | 'disconnected';

    switch (serviceState.status) {
      case ConnectionStatus.CONNECTED:
        statusString = 'connected';
        break;
      case ConnectionStatus.CONNECTING:
        statusString = 'connecting';
        break;
      case ConnectionStatus.RECOVERING:
        statusString = 'recovering';
        break;
      case ConnectionStatus.DISCONNECTED:
      default:
        statusString = 'disconnected';
        break;
    }

    return {
      status: statusString,
      quality: this.currentConnectionQuality, // Use internal WS quality metric
      error: serviceState.error
    };
  }

  /**
   * Checks if the WebSocket is currently in the process of connecting or recovering.
   * @returns True if connecting or recovering, false otherwise.
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
