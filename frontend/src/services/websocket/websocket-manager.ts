// src/services/websocket/websocket-manager.ts
import { config } from '../../config';
import { EventEmitter } from '../../utils/event-emitter';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { CircuitBreaker, CircuitState } from '../../utils/circuit-breaker';
import { TokenManager } from '../auth/token-manager';
import { ConnectionStrategy } from './connection-strategy';
import { HeartbeatManager } from './heartbeat-manager';
import { ErrorHandler, ErrorSeverity } from '../../utils/error-handler';
import { WebSocketMessageHandler } from './message-handler';
import { DeviceIdManager } from '../../utils/device-id-manager';
import { MetricTracker } from './metric-tracker';
import { Logger } from '../../utils/logger';
import {
  WebSocketOptions,
  ConnectionMetrics,
  DataSourceConfig, // Keep if used for alternative sources
  ConnectionQuality as WSConnectionQuality, // Alias to avoid clash
  HeartbeatData
} from './types';
import {
  WebSocketError,
  NetworkError,
  AuthenticationError,
  WebSocketErrorHandler
} from './websocket-error';
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus,
  ConnectionQuality // Use unified quality enum
} from '../connection/unified-connection-state';
import { Disposable } from '../../utils/disposable'; // Import Disposable

// Make WebSocketManager implement Disposable
export class WebSocketManager extends EventEmitter implements Disposable {
  private connectionStrategy: ConnectionStrategy;
  private heartbeatManager: HeartbeatManager | null = null;
  private messageHandler: WebSocketMessageHandler;
  private tokenManager: TokenManager;
  private metricTracker: MetricTracker;
  private errorHandler: WebSocketErrorHandler;
  private logger: Logger; // Use Logger instance
  private unifiedState: UnifiedConnectionState;

  private backoffStrategy: BackoffStrategy;
  private circuitBreaker: CircuitBreaker;
  private reconnectTimer: number | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10; // Default, consider making configurable
  private isDisposed: boolean = false; // Track disposal state


  private connectionMetrics: ConnectionMetrics = {
    latency: 0,
    bandwidth: 0, // Note: Bandwidth calculation might be complex/inaccurate in browser
    packetLoss: 0 // Note: Packet loss calculation is often an estimation
  };

  // Removed dataSources - logic for alternative sources seems complex and potentially outdated
  // private currentDataSource: DataSourceConfig;
  private currentConnectionQuality: WSConnectionQuality = WSConnectionQuality.DISCONNECTED; // Use aliased enum

  constructor(
    tokenManager: TokenManager,
    unifiedState: UnifiedConnectionState,
    logger: Logger, // Inject logger instance
    options: WebSocketOptions = {} // Use provided options interface
  ) {
    super();
    this.tokenManager = tokenManager;
    this.unifiedState = unifiedState;
    // Assign the injected logger instance
    this.logger = logger; // No need for new Logger() or createChild here
    this.logger.info("WebSocketManager Initializing...");

    // Initialize sub-components, passing the logger
    this.metricTracker = new MetricTracker(this.logger); // Pass logger if MetricTracker accepts it
    this.errorHandler = new WebSocketErrorHandler(this.logger); // Pass logger

    this.backoffStrategy = new BackoffStrategy(
        options.reconnectInitialDelay ?? 1000, // Use options or defaults
        options.reconnectMaxDelay ?? 30000
    );
    this.circuitBreaker = new CircuitBreaker(
        'websocket-connection',
        options.failureThreshold ?? 5,
        options.resetTimeoutMs ?? 60000
    );
     // Log circuit breaker state changes
    this.circuitBreaker.onStateChange((name, oldState, newState, info) => {
        this.logger.warn(`Circuit Breaker [${name}] state changed: ${oldState} -> ${newState}`, info);
         if (newState === CircuitState.OPEN) {
             ErrorHandler.handleConnectionError(
                'Multiple WebSocket connection failures. Connection attempts temporarily suspended.',
                ErrorSeverity.HIGH,
                'WebSocket'
             );
         }
    });


    // this.currentDataSource = this.dataSources[0]; // Removed datasource logic

    // Pass necessary dependencies to ConnectionStrategy
    this.connectionStrategy = new ConnectionStrategy({
      tokenManager,
      eventEmitter: this, // Pass this instance as the event emitter
      options // Pass along WebSocketOptions
    });

    // Pass necessary dependencies to MessageHandler
    this.messageHandler = new WebSocketMessageHandler(this, this.logger); // Pass logger if needed

    this.maxReconnectAttempts = options.reconnectMaxAttempts ?? 10;

    this.setupListeners(); // Renamed for clarity
    // this.monitorConnection(); // Removed - monitoring logic seems complex and potentially overlapping
    this.logger.info("WebSocketManager Initialized.");
  }

  // Centralized setup for internal event listeners
  private setupListeners(): void {
    this.logger.info("Setting up WebSocketManager listeners...");
    // Listen for internal events emitted by this class or sub-components
    this.on('error', this.handleComprehensiveError.bind(this));
    this.on('disconnected', this.handleDisconnectEvent.bind(this)); // Renamed internal handler

    // Listen for events from sub-components if they emit directly
    // Example: if ConnectionStrategy emitted 'connection_error'
    // this.connectionStrategy.on('connection_error', this.handleConnectionError.bind(this));

    // Forward heartbeat events to unified state (and handle locally if needed)
    this.on('heartbeat', this.handleHeartbeatEvent.bind(this));
    this.on('heartbeat_timeout', this.handleHeartbeatTimeout.bind(this));

    // Listen for session invalidation from message handler
    this.on('session_invalidated', this.handleSessionInvalidated.bind(this));

    // Listen for force logout event (e.g., triggered by auth errors)
     this.on('force_logout', (reason: string) => {
         this.logger.warn(`Force logout event received: ${reason}`);
         // Ensure disconnection on force logout
         this.disconnect('force_logout');
     });
  }


  // Handles the 'disconnected' event emitted internally or by ConnectionStrategy
  private handleDisconnectEvent(details: { code: number; reason: string; wasClean: boolean }): void {
    if (this.isDisposed) return;
    this.logger.warn(`WebSocket disconnected event received. Code: ${details.code}, Reason: ${details.reason}, Clean: ${details.wasClean}`);

    // Stop heartbeat on any disconnect
    this.heartbeatManager?.stop();
    this.heartbeatManager = null;

    // Update unified state
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
      status: ConnectionStatus.DISCONNECTED,
      error: details.reason || `WebSocket closed (Code: ${details.code})`
    });

    // Decide whether to reconnect based on the close code and reason
    // Standard close code 1000 usually means intentional close, no reconnect needed.
    // Other codes (e.g., 1001 Going Away, 1006 Abnormal Closure) usually warrant reconnect.
    const shouldReconnect = details.code !== 1000; // Simple check, might need refinement

    if (shouldReconnect) {
        this.logger.info('Disconnect requires reconnection attempt.');
      this.attemptReconnect();
    } else {
        this.logger.info('Disconnect was clean or intentional, no automatic reconnect.');
        // Ensure reconnect attempts are reset if disconnect was clean
        this.reconnectAttempts = 0;
        this.backoffStrategy.reset();
        this.circuitBreaker.reset(); // Reset circuit breaker on clean disconnect
        this.unifiedState.updateRecovery(false, 0); // Ensure recovery state is cleared
    }
  }

  // Handles connection errors (e.g., initial connection failure, network issues during connection)
  private handleConnectionError(error: Error): void {
     if (this.isDisposed) return;
    this.logger.error('WebSocket connection error occurred:', { message: error.message, name: error.name });

    // Update unified state with error
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
      status: ConnectionStatus.DISCONNECTED, // Ensure status reflects failure
      error: error.message || 'WebSocket connection failed'
    });

    // Use standardized error handler
    ErrorHandler.handleConnectionError(
      error,
      ErrorSeverity.MEDIUM, // Or HIGH depending on context
      'WebSocket'
    );

    // Attempt to reconnect after a connection error
    this.attemptReconnect();
  }

   // Handles the 'heartbeat' event (likely a response from server)
  private handleHeartbeatEvent(data: HeartbeatData): void {
     if (this.isDisposed) return;
    // Notify heartbeat manager that a response was received
    this.heartbeatManager?.handleHeartbeatResponse();

    const now = Date.now();
    const latency = now - data.timestamp; // Calculate latency based on server timestamp in response

    // Update the unified state with heartbeat data
    this.unifiedState.updateHeartbeat(now, latency);

    // If simulator status is included in heartbeat, update it
    if (data.simulatorStatus) {
      this.unifiedState.updateSimulatorStatus(data.simulatorStatus);
    }

    // Update local connection quality based on latency
    this.updateConnectionQuality(latency);
  }

  // Handle heartbeat timeout event
  private handleHeartbeatTimeout(): void {
      if (this.isDisposed) return;
      this.logger.error('Heartbeat timeout detected. Server may be unresponsive.');
      ErrorHandler.handleConnectionError(
          'Connection to server lost (heartbeat timeout).',
          ErrorSeverity.HIGH,
          'WebSocket Heartbeat'
      );
      // Treat timeout as a disconnect and attempt recovery
      this.connectionStrategy.disconnect(); // Force close the socket
      // The 'disconnected' event handler will then trigger attemptReconnect
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.DISCONNECTED,
          error: 'Heartbeat timeout'
      });
      this.attemptReconnect(); // Explicitly trigger reconnect here as well
  }

  // Handle session invalidation message from server
  private handleSessionInvalidated(details: { reason: string }): void {
       if (this.isDisposed) return;
       this.logger.error(`Session invalidated by server. Reason: ${details.reason}`);
       ErrorHandler.handleAuthError(
           `Session invalidated: ${details.reason}. Please log in again.`,
           ErrorSeverity.HIGH
       );
       this.triggerLogout(`session_invalidated: ${details.reason}`);
  }


  // Maps internal error types/codes to severity for ErrorHandler
  private getErrorSeverity(errorCode: string | undefined): ErrorSeverity {
    switch (errorCode) {
      case 'UNAUTHORIZED':
      case 'AUTH_FAILED':
      case 'TOKEN_EXPIRED':
        return ErrorSeverity.HIGH;
      case 'CONNECTION_FAILED':
      case 'NETWORK_ERROR':
        return ErrorSeverity.MEDIUM;
      case 'PROTOCOL_ERROR':
        return ErrorSeverity.HIGH;
      case 'RATE_LIMIT':
        return ErrorSeverity.MEDIUM;
      default:
        return ErrorSeverity.MEDIUM; // Default severity
    }
  }

  // Central handler for various error types
  private handleComprehensiveError(error: any): void {
     if (this.isDisposed) return;
    this.logger.error("Handling comprehensive error", { error });

    let severity = ErrorSeverity.MEDIUM;
    let context = 'WebSocket';
    let errorMessage = 'An unknown WebSocket error occurred';
    let errorCode: string | undefined = undefined;

    if (error instanceof WebSocketError) {
        severity = this.getErrorSeverity(error.code);
        context = `WebSocket (${error.code})`;
        errorMessage = error.message;
        errorCode = error.code;
        ErrorHandler.handleConnectionError(error, severity, context); // Use connection handler

         // Specific actions based on WebSocket error code
         if (error.code === 'UNAUTHORIZED' || error.code === 'AUTH_FAILED') {
             this.errorHandler.handleAuthenticationError(new AuthenticationError(error.message), {
                 tokenManager: this.tokenManager,
                 manualReconnect: this.manualReconnect.bind(this),
                 triggerLogout: this.triggerLogout.bind(this)
             });
         } else if (error.code === 'PROTOCOL_ERROR') {
             this.disconnect('protocol_error'); // Disconnect on protocol errors
         } else {
             // General WebSocket errors trigger reconnect
             this.attemptReconnect();
         }

    } else if (error instanceof NetworkError) {
        severity = ErrorSeverity.MEDIUM;
        context = `Network (${error.type})`;
        errorMessage = error.message;
        ErrorHandler.handleConnectionError(error, severity, context);
        // Network errors trigger reconnect
        this.attemptReconnect();
        // Removed alternative data source logic
        // this.errorHandler.handleNetworkError(error, { ... });

    } else if (error instanceof AuthenticationError) {
        severity = ErrorSeverity.HIGH;
        context = 'Authentication';
        errorMessage = error.message;
        ErrorHandler.handleAuthError(error, severity, context);
        this.errorHandler.handleAuthenticationError(error, {
            tokenManager: this.tokenManager,
            manualReconnect: this.manualReconnect.bind(this),
            triggerLogout: this.triggerLogout.bind(this)
        });
    } else if (error instanceof Error) {
        // Generic JavaScript Error
        severity = ErrorSeverity.HIGH; // Assume high for unknown errors
        context = 'WebSocket (Unknown)';
        errorMessage = error.message;
        ErrorHandler.handleConnectionError(error, severity, context);
        // Attempt reconnect for unknown errors
        this.attemptReconnect();
    } else {
         // Non-Error type thrown
         severity = ErrorSeverity.HIGH;
         context = 'WebSocket (Unknown)';
         errorMessage = String(error);
         ErrorHandler.handleConnectionError(errorMessage, severity, context);
         this.attemptReconnect();
    }

    // Update unified state with the error details
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
      // Keep status as DISCONNECTED or RECOVERING based on attemptReconnect call
      error: `${context}: ${errorMessage}`
    });
  }

  // Triggers logout process
  private triggerLogout(reason: string = 'unknown'): void {
     if (this.isDisposed) return;
    this.logger.warn(`Triggering logout. Reason: ${reason}`);
    this.disconnect(`logout: ${reason}`); // Ensure WS is disconnected
    this.tokenManager.clearTokens(); // Clear stored tokens
    // ErrorHandler.handleAuthError('Session ended. Please log in again.', ErrorSeverity.HIGH); // Maybe too noisy if logout is intentional
    this.emit('force_logout', reason); // Emit event for UI/AuthContext to handle
  }

  // Removed initiateOfflineMode - requires more complex offline handling logic

  // Removed checkSessionReady - specific logic, depends on backend implementation

  // Removed monitorConnection - simplified, quality updated on heartbeat

  // Update local quality state and unified state quality
  private updateConnectionQuality(latency: number): void {
     if (this.isDisposed) return;
    const newQuality = this.calculateWsConnectionQuality(latency); // Use internal calculation

    if (newQuality !== this.currentConnectionQuality) {
      this.logger.info(`WebSocket connection quality changed: ${this.currentConnectionQuality} -> ${newQuality}`);
      this.currentConnectionQuality = newQuality;
      this.emit('connection_quality_changed', this.currentConnectionQuality); // Emit specific WS quality

      // Map WS quality to unified quality enum
      let unifiedQuality: ConnectionQuality;
      switch (newQuality) {
        case WSConnectionQuality.EXCELLENT:
        case WSConnectionQuality.GOOD:
          unifiedQuality = ConnectionQuality.GOOD;
          break;
        case WSConnectionQuality.FAIR:
          unifiedQuality = ConnectionQuality.DEGRADED;
          break;
        case WSConnectionQuality.POOR:
        case WSConnectionQuality.DISCONNECTED:
          unifiedQuality = ConnectionQuality.POOR;
          break;
        default:
          unifiedQuality = ConnectionQuality.UNKNOWN;
      }

      // Update unified state quality (handled within updateHeartbeat now)
      // this.unifiedState.updateQuality(unifiedQuality); // Assuming UnifiedState has updateQuality
    }
  }

  // Internal calculation for WebSocket-specific quality levels
  private calculateWsConnectionQuality(latency: number): WSConnectionQuality {
    if (latency < 0) return WSConnectionQuality.DISCONNECTED; // Or UNKNOWN
    // Adjust thresholds as needed
    if (latency <= 100) return WSConnectionQuality.EXCELLENT;
    if (latency <= 300) return WSConnectionQuality.GOOD;
    if (latency <= 800) return WSConnectionQuality.FAIR;
    return WSConnectionQuality.POOR;
  }

  // Removed tryAlternativeDataSource and related connection methods (connectSSE, connectREST)

  /**
   * Establishes the WebSocket connection using the ConnectionStrategy.
   * Handles circuit breaker logic.
   * @returns True if connection is successful, false otherwise.
   */
  public async connect(): Promise<boolean> {
     if (this.isDisposed) {
        this.logger.error("Cannot connect: WebSocketManager is disposed.");
        return false;
     }
    this.logger.info("WebSocket connect requested.");

    // Update unified state to connecting
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
      status: ConnectionStatus.CONNECTING,
      error: null,
      recoveryAttempts: this.reconnectAttempts // Reflect current attempt if reconnecting
    });

    try {
      // Execute connection logic within the circuit breaker
      const ws = await this.circuitBreaker.execute(async () => {
        try {
          // Ensure device ID exists before connecting
          DeviceIdManager.getDeviceId(); // Ensures ID is generated and stored if needed

          const webSocket = await this.connectionStrategy.connect(); // Use the strategy to connect

          // --- Setup WebSocket Event Handlers ---
          webSocket.onmessage = (event) => this.messageHandler.handleMessage(event);

          webSocket.onerror = (event) => {
             // Handle onerror - often precedes onclose for connection failures
             this.logger.error('WebSocket onerror event received.', event);
             // Emit a specific error type, don't throw directly from event handler
             this.emit('error', new WebSocketError('WebSocket onerror event', 'CONNECTION_FAILED'));
             // Don't attempt reconnect here, let onclose handle it
          };

          webSocket.onclose = (event) => {
             // Handle onclose - provides close code and reason
             this.logger.warn(`WebSocket onclose event received. Code: ${event.code}, Reason: ${event.reason}, Clean: ${event.wasClean}`);
             // Emit the 'disconnected' event with details for handleDisconnectEvent
             this.emit('disconnected', { code: event.code, reason: event.reason, wasClean: event.wasClean });
             // Reconnect logic is handled in handleDisconnectEvent
          };
          // --------------------------------------

          return webSocket; // Return the WebSocket instance on success

        } catch (connectionError: unknown) {
           // Catch errors during connectionStrategy.connect() itself
          const error = connectionError instanceof Error ? connectionError : new Error(String(connectionError));
          this.logger.error('Failed to establish WebSocket connection via strategy.', { error: error.message });
          // Throw the error again so the circuit breaker catches it
          throw new WebSocketError(error.message, 'CONNECTION_FAILED');
        }
      });

      // --- Connection Successful ---
      this.logger.info("WebSocket connection established successfully.");

      // Start heartbeat mechanism
      this.heartbeatManager = new HeartbeatManager({
        ws, // Pass the established WebSocket
        eventEmitter: this, // Pass this manager as emitter
        options: { // Pass heartbeat options if available
            interval: this.connectionStrategy.options.heartbeatInterval,
            timeout: this.connectionStrategy.options.heartbeatTimeout
        }
      });
      this.heartbeatManager.start();

      // Clear any pending reconnect timer
      this.stopReconnectTimer();
      this.reconnectAttempts = 0; // Reset attempts on successful connect
      this.backoffStrategy.reset(); // Reset backoff on successful connect
      // Circuit breaker is reset automatically by successful execute

      // Update unified state to connected
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        status: ConnectionStatus.CONNECTED,
        lastConnected: Date.now(),
        error: null,
        recoveryAttempts: 0 // Reset recovery attempts in state
      });
      this.unifiedState.updateRecovery(false, 0); // Ensure recovery overlay is hidden

      return true; // Signal successful connection

    } catch (error: any) {
      // --- Connection Failed (Circuit Breaker Open or Strategy Error) ---
      this.logger.error(`WebSocket connection failed overall. Reason: ${error.message}`);
      this.emit('error', error); // Emit the error for comprehensive handling

      // Update unified state to reflect disconnected status after failure
       this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
         status: ConnectionStatus.DISCONNECTED,
         error: error.message || 'Connection failed'
       });

       // If the error was *not* the circuit breaker being open, trigger reconnect attempt
       if (this.circuitBreaker.getState() !== CircuitState.OPEN) {
           this.attemptReconnect();
       }

      return false; // Signal connection failure
    }
  }

  /**
   * Sends a message over the WebSocket connection if open.
   * @param message - The message object to send (will be JSON.stringified).
   * @throws {Error} If the WebSocket is not open.
   */
  public send(message: any): void {
     if (this.isDisposed) {
        this.logger.error("Cannot send message: WebSocketManager is disposed.");
        throw new Error("WebSocketManager is disposed.");
     }
    const ws = this.connectionStrategy.getWebSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
        try {
            ws.send(JSON.stringify(message));
            // Avoid logging potentially sensitive message content by default
            // this.logger.info('WebSocket message sent', { type: message?.type });
        } catch (error: any) {
             this.logger.error('Failed to send WebSocket message', { error: error.message });
             throw error; // Re-throw send errors
        }
    } else {
      this.logger.error('Cannot send message, WebSocket is not open.', { readyState: ws?.readyState });
      throw new Error(`WebSocket is not open. ReadyState: ${ws?.readyState ?? 'N/A'}`);
    }
  }

  /**
   * Disconnects the WebSocket connection intentionally.
   * @param reason - A string indicating the reason for disconnection.
   */
  public disconnect(reason: string = 'user_disconnect'): void {
     if (this.isDisposed) return;
    this.logger.warn(`WebSocket disconnect requested. Reason: ${reason}`);
    this.stopReconnectTimer(); // Stop any pending reconnect attempts
    this.heartbeatManager?.stop(); // Stop heartbeats
    this.heartbeatManager = null;
    this.connectionStrategy.disconnect(); // Tell strategy to close the socket

    // Update state immediately, don't wait for onclose if intentional
     this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
       status: ConnectionStatus.DISCONNECTED,
       error: reason
     });

    // Reset resilience mechanisms on intentional disconnect
    this.reconnectAttempts = 0;
    this.backoffStrategy.reset();
    this.circuitBreaker.reset();
    this.unifiedState.updateRecovery(false, 0);

    // Emit disconnected event *after* internal state is updated
    // Note: connectionStrategy.disconnect() might also trigger the 'onclose' -> 'disconnected' event.
    // Be mindful of potential double emissions if not handled carefully.
    // Consider adding a flag to handleDisconnectEvent to ignore if reason is 'user_disconnect'.
    // this.emit('disconnected', { code: 1000, reason: reason, wasClean: true });
  }

  /**
   * Cleans up resources used by the WebSocketManager.
   */
  public dispose(): void {
     if (this.isDisposed) return;
     this.logger.warn("Disposing WebSocketManager...");
     this.isDisposed = true;

    this.disconnect('manager_disposed'); // Disconnect socket and stop timers

    // Clean up event listeners specific to this class
    this.removeAllListeners(); // From EventEmitter base class

    // Dispose sub-components if they have dispose methods
    // (Assuming ConnectionStrategy doesn't need disposal)
    // if (this.messageHandler instanceof Disposable) { // Check if MessageHandler implements Disposable
    //    this.messageHandler.dispose();
    // }
    // MetricTracker disposal was removed as it didn't have the method

     // Remove circuit breaker listeners to prevent memory leaks
     this.circuitBreaker.removeStateChangeListener(); // Assuming a method like this exists

    this.logger.warn("WebSocketManager disposed.");
  }

  // Method to explicitly stop any active reconnect timer
  private stopReconnectTimer(): void {
      if (this.reconnectTimer !== null) {
        this.logger.info('Stopping reconnect timer.');
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
  }

  /**
   * Attempts to reconnect the WebSocket connection after a delay.
   * Uses backoff strategy and respects circuit breaker state.
   */
  private attemptReconnect(): void {
     if (this.isDisposed || this.reconnectTimer !== null) {
         if(this.isDisposed) this.logger.warn('Reconnect attempt aborted: Manager disposed.');
         if(this.reconnectTimer !== null) this.logger.warn('Reconnect attempt aborted: Already scheduled.');
         return; // Already trying to reconnect or disposed
     }

    // Check circuit breaker state
    if (this.circuitBreaker.getState() === CircuitState.OPEN) {
      this.logger.warn('Reconnect attempt aborted: Circuit breaker is OPEN.');
      // No need to schedule if circuit is open
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          // Ensure state reflects disconnected if circuit is open
          status: ConnectionStatus.DISCONNECTED,
          error: 'Connection failed (Circuit Breaker Open)'
      });
      this.unifiedState.updateRecovery(false, 0); // Not actively recovering if CB is open
      return;
    }

    // Check max attempts
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.logger.error(`Reconnect attempt aborted: Max reconnect attempts (${this.maxReconnectAttempts}) reached.`);
       ErrorHandler.handleConnectionError(
             `Failed to reconnect WebSocket after ${this.maxReconnectAttempts} attempts. Giving up.`,
             ErrorSeverity.HIGH,
             'WebSocket'
           );
       this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
           status: ConnectionStatus.DISCONNECTED,
           error: `Failed to reconnect after ${this.maxReconnectAttempts} attempts.`
       });
       this.unifiedState.updateRecovery(false, 0); // Recovery failed
      return;
    }

    this.reconnectAttempts++;
    const delay = this.backoffStrategy.nextBackoffTime();
    this.logger.info(`Scheduling WebSocket reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts} in ${delay}ms.`);


    // Update unified state to show recovery is in progress
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        status: ConnectionStatus.RECOVERING, // Use RECOVERING status
        error: `Attempting to reconnect (attempt ${this.reconnectAttempts})...`,
        recoveryAttempts: this.reconnectAttempts
    });
    this.unifiedState.updateRecovery(true, this.reconnectAttempts); // Signal recovery UI

    this.emit('reconnecting', { // Emit event for potential UI feedback
      attempt: this.reconnectAttempts,
      maxAttempts: this.maxReconnectAttempts,
      delay
    });

    // Schedule the reconnect attempt
    this.reconnectTimer = window.setTimeout(async () => {
      this.reconnectTimer = null; // Clear timer ID before attempting connect
      this.logger.info(`Executing scheduled WebSocket reconnect attempt ${this.reconnectAttempts}.`);
      await this.connect(); // Attempt to connect
      // No need to call attemptReconnect again here; if connect() fails, it handles the next step.
    }, delay);
  }

  /**
   * Initiates a manual reconnection attempt immediately.
   * Resets backoff and circuit breaker state.
   */
  public manualReconnect(): void {
     if (this.isDisposed) {
         this.logger.error("Cannot manual reconnect: WebSocketManager is disposed.");
         return;
     }
    this.logger.warn('Manual reconnect requested.');
    this.stopReconnectTimer(); // Cancel any pending automatic reconnect
    this.reconnectAttempts = 0; // Reset attempt counter for manual trigger
    this.backoffStrategy.reset();
    this.circuitBreaker.reset(); // Force circuit breaker closed

    // Update state to show recovery initiated manually
    this.unifiedState.updateRecovery(true, 1); // Signal recovery UI, start attempt count at 1

    // Immediately attempt to connect
    this.connect();
  }

  /**
   * Gets the current health status of the WebSocket connection.
   * @returns An object containing status, quality, and error information.
   */
  public getConnectionHealth() {
     if (this.isDisposed) {
         return { status: 'disconnected', quality: WSConnectionQuality.DISCONNECTED, error: 'Manager disposed' };
     }
    const ws = this.connectionStrategy.getWebSocket();
    const state = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);

    let status: 'connected' | 'connecting' | 'recovering' | 'disconnected';
    switch(state.status) {
        case ConnectionStatus.CONNECTED: status = 'connected'; break;
        case ConnectionStatus.CONNECTING: status = 'connecting'; break;
        case ConnectionStatus.RECOVERING: status = 'recovering'; break;
        case ConnectionStatus.DISCONNECTED:
        default: status = 'disconnected'; break;
    }

    return {
      status: status,
      quality: this.currentConnectionQuality, // Use internal WS quality
      error: state.error
    };
  }

  /**
   * Checks if the WebSocket is currently in the process of connecting or reconnecting.
   * @returns True if connecting or recovering, false otherwise.
   */
  public isConnectingOrRecovering(): boolean {
     if (this.isDisposed) return false;
    const state = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    return state.status === ConnectionStatus.CONNECTING || state.status === ConnectionStatus.RECOVERING;
  }

   // Implement [Symbol.dispose] for Disposable interface
   [Symbol.dispose](): void {
       this.dispose();
   }
}
