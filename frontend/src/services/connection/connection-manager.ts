// src/services/connection/connection-manager.ts

// --- Core Dependencies ---
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { ExchangeDataStream } from '../sse/exchange-data-stream';
import { HttpClient } from '../../api/http-client';
import { ConnectionRecoveryInterface } from './connection-recovery-interface';
import { RecoveryManager } from './recovery-manager';
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus,
  ServiceState // Ensure ServiceState is exported from unified-connection-state.ts
} from './unified-connection-state';
import { ConnectionDataHandlers } from './connection-data-handlers';
import { ConnectionSimulatorManager } from './connection-simulator';
import { Logger } from '../../utils/logger';
import { Disposable } from '../../utils/disposable';
// +++ ADDED: Import SessionApi +++
import { SessionApi } from '../../api/session';
// +++ ADDED: Import ErrorHandler and ErrorSeverity for error handling +++
import { ErrorHandler, ErrorSeverity } from '../../utils/error-handler';
// +++ ADDED: Import ToastService to pass to ErrorHandler +++
import { toastService } from '../notification/toast-service'; // Assuming singleton instance


/**
 * Orchestrates all client-side connections (WebSocket, SSE, REST via HttpClient)
 * and manages overall connection state, recovery, and data flow.
 */
export class ConnectionManager extends EventEmitter implements ConnectionRecoveryInterface, Disposable {
  // --- Private Member Variables ---
  private unifiedState: UnifiedConnectionState;
  private dataHandlers: ConnectionDataHandlers;
  private simulatorManager: ConnectionSimulatorManager;
  private recoveryManager: RecoveryManager;
  private wsManager: WebSocketManager;
  private sseManager: ExchangeDataStream;
  private tokenManager: TokenManager;
  private logger: Logger;
  private isDisposed: boolean = false;
  // +++ ADDED: Instance variable for SessionApi +++
  private sessionApi: SessionApi;
  // +++ ADDED: Instance variable for ErrorHandler +++
  private errorHandler: ErrorHandler;


  /**
   * Creates an instance of ConnectionManager.
   * @param tokenManager - The TokenManager instance for authentication.
   * @param logger - The Logger instance for logging.
   * @param wsOptions - Optional configuration for WebSocketManager.
   * @param sseOptions - Optional configuration for SSEManager (passed via ExchangeDataStream).
   */
  constructor(
    tokenManager: TokenManager,
    logger: Logger,
    wsOptions: ConstructorParameters<typeof WebSocketManager>[3] = {}, // Get options type from WebSocketManager
    sseOptions: ConstructorParameters<typeof ExchangeDataStream>[3] = {} // Get options type from ExchangeDataStream
  ) {
    super();

    this.logger = logger; // Use the passed-in logger directly
    this.logger.info('ConnectionManager Initializing...');

    // --- Assign Core Dependencies ---
    this.tokenManager = tokenManager;
    this.errorHandler = new ErrorHandler(this.logger, toastService); // Ensure this exists
    
    // --- Instantiate State and Error Handling ---
    this.unifiedState = new UnifiedConnectionState(this.logger);
    // +++ ADDED: Instantiate ErrorHandler (verify dependencies) +++
    // Pass the logger instance and the singleton toastService instance
    this.errorHandler = new ErrorHandler(this.logger, toastService);

    // --- Instantiate API Clients and Sub-Managers ---
    const httpClient = new HttpClient(tokenManager); // Assuming HttpClient only needs tokenManager
    // +++ ADDED: Instantiate SessionApi +++
    this.sessionApi = new SessionApi(httpClient);

    // Instantiate WebSocket manager, passing dependencies and options
    this.wsManager = new WebSocketManager(
      tokenManager,
      this.unifiedState,
      this.logger, // Pass logger instance
      wsOptions // Pass WebSocket options
    );

    // *** FIX: Pass WebSocketManager instance and Logger to ExchangeDataStream ***
    // Also pass through SSE-specific options if needed
    this.sseManager = new ExchangeDataStream(
      tokenManager,
      this.unifiedState,
      this.logger, // Pass logger instance
      this.errorHandler, // <-- Pass instance here
      sseOptions // Pass SSE options (like reconnect attempts)
    );

    // --- Instantiate Helper Managers ---
    // *** FIX: Inject ErrorHandler instance into ConnectionDataHandlers ***
    this.dataHandlers = new ConnectionDataHandlers(httpClient, this.errorHandler);
    this.simulatorManager = new ConnectionSimulatorManager(httpClient);
    this.recoveryManager = new RecoveryManager(
      this, // ConnectionRecoveryInterface implementation
      tokenManager,
      this.unifiedState
    );

    // --- Setup Event Listeners ---
    this.setupEventListeners();
    this.logger.info('ConnectionManager Initialization Complete.');
  }

  /**
   * Sets up internal event listeners for sub-managers and state changes.
   */
  private setupEventListeners(): void {
    this.logger.info('Setting up ConnectionManager event listeners...');

    // --- State Change Listener ---
    // Forward unified state changes for external consumers (e.g., UI)
    this.unifiedState.on('state_change', (state: ReturnType<UnifiedConnectionState['getState']>) => {
      if (this.isDisposed) return;
      this.emit('state_change', { current: state }); // Emit the full state object

      // --- Derived Events based on State ---
      // Emit 'connected' when overall status becomes CONNECTED
      if (state.overallStatus === ConnectionStatus.CONNECTED) {
          // Check previous state if needed to avoid multiple emits, or rely on listener idempotency
          this.emit('connected');
      }
      // Emit 'disconnected' when overall status becomes DISCONNECTED
      else if (state.overallStatus === ConnectionStatus.DISCONNECTED) {
          // Determine primary reason for disconnect (e.g., WS error, SSE error, manual)
          const wsError = state.webSocketState.error;
          const sseError = state.sseState.error;
          const reason = wsError || sseError || 'disconnected';
          this.emit('disconnected', { reason });
      }
    });

    // --- WebSocket State Listener (for logging specific changes) ---
    this.unifiedState.on('websocket_state_change', ({ state }: { state: ServiceState }) => {
        if (this.isDisposed) return;
        if (state.status === ConnectionStatus.CONNECTED || state.status === ConnectionStatus.DISCONNECTED) {
            this.logger.info(`WebSocket state changed to: ${state.status}`, { error: state.error });
        }
    });

     // --- SSE State Listener (for logging specific changes) ---
     this.unifiedState.on('sse_state_change', ({ state }: { state: ServiceState }) => {
         if (this.isDisposed) return;
         if (state.status === ConnectionStatus.CONNECTED || state.status === ConnectionStatus.DISCONNECTED) {
            this.logger.info(`SSE state changed to: ${state.status}`, { error: state.error });
         }
     });

    // --- Data Event Listeners from SSE Manager ---
    // Forward specific data events for external consumers
    this.sseManager.on('exchange-data', (data: any) => {
      if (this.isDisposed) return;
      this.dataHandlers.updateExchangeData(data); // Update internal cache if needed
      this.emit('exchange_data', data);
    });

    this.sseManager.on('order-update', (data: any) => {
       if (this.isDisposed) return;
       this.logger.info('Received order update via SSE.');
       this.emit('order_update', data);
    });
    // Add listeners for other SSE events as needed

    // --- Recovery Event Listeners ---
    // Forward recovery events for external consumers
    this.recoveryManager.on('recovery_attempt', (data: any) => {
      if (this.isDisposed) return;
      this.logger.warn('Connection recovery attempt started', data);
      this.emit('recovery_attempt', data);
    });
    this.recoveryManager.on('recovery_success', () => {
      if (this.isDisposed) return;
      this.logger.info('Connection recovery successful.');
      this.emit('recovery_success');
    });
    this.recoveryManager.on('recovery_failed', (data?: any) => { // Make data optional
      if (this.isDisposed) return;
      this.logger.error('Connection recovery failed.', data);
      this.emit('recovery_failed', data);
    });

    // --- Authentication Listener ---
    // Listen for token refresh events to manage auth state
    this.tokenManager.addRefreshListener(this.handleTokenRefresh);

    this.logger.info('ConnectionManager event listeners setup complete.');
  }

  // --- Lifecycle & State Methods ---

  /**
   * Disposes of the ConnectionManager and all its sub-managers, cleaning up resources.
   */
  public dispose(): void {
    if (this.isDisposed) {
      this.logger.warn('ConnectionManager already disposed.');
      return;
    }
    this.logger.warn('Disposing ConnectionManager...');
    this.isDisposed = true;

    // Ensure underlying connections are closed first
    this.disconnect('manager_disposed');

    // Helper to safely call dispose methods
    const tryDispose = (manager: any) => {
      if (!manager) return;
      try {
        if (typeof manager[Symbol.dispose] === 'function') {
          manager[Symbol.dispose]();
        } else if (typeof manager.dispose === 'function') {
          manager.dispose();
        }
      } catch (error) {
        this.logger.error('Error during sub-manager disposal', { manager: manager?.constructor?.name, error });
      }
    };

    // Dispose managers in reverse order of dependency (or safe order)
    tryDispose(this.recoveryManager);
    tryDispose(this.sseManager); // Depends on WSManager, UnifiedState
    tryDispose(this.wsManager); // Depends on UnifiedState, TokenManager
    tryDispose(this.unifiedState);
    // Dispose others if they implement Disposable
    // tryDispose(this.dataHandlers);
    // tryDispose(this.simulatorManager);
    // tryDispose(this.errorHandler); // If it needs disposal

    // Clean up listeners
    if (this.tokenManager) {
      try {
        this.tokenManager.removeRefreshListener(this.handleTokenRefresh);
      } catch (error) {
        this.logger.error('Error removing token refresh listener', { error });
      }
    }
    this.removeAllListeners(); // From EventEmitter base

    this.logger.warn('ConnectionManager disposed.');
  }

  /**
   * Attempts to establish a connection by validating the session and connecting WebSocket.
   * SSE connection will be triggered automatically if WebSocket connects successfully.
   * @returns A promise resolving to true if the connection (including session validation) is successful, false otherwise.
   */
  public async connect(): Promise<boolean> {
    if (this.isDisposed) {
      this.logger.error("Cannot connect: ConnectionManager is disposed.");
      return false;
    }
    this.logger.info('Connection attempt requested via ConnectionManager.');

    // --- Check Authentication ---
    const token = await this.tokenManager.getAccessToken(); // Ensures token is fresh if possible
    if (!token) {
      this.logger.error('Connection Aborted: Authentication token not available.');
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        status: ConnectionStatus.DISCONNECTED,
        error: 'Authentication required'
      });
      this.emit('auth_failed', 'Authentication required');
      return false;
    }

    // --- Check Current State ---
    const currentState = this.unifiedState.getState();
    if (currentState.isConnected || currentState.isConnecting || currentState.isRecovering) {
      this.logger.warn(`Connect call ignored: Already ${currentState.overallStatus}.`);
      return currentState.isConnected;
    }

    // --- Session Validation Step ---
    try {
      this.logger.info('Attempting to create or validate session...');
      // Update state to connecting before async calls
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, { status: ConnectionStatus.CONNECTING, error: null });
      this.unifiedState.updateServiceState(ConnectionServiceType.SSE, { status: ConnectionStatus.CONNECTING, error: null }); // Assume SSE will try too

      const sessionResponse = await this.sessionApi.createSession();
      if (!sessionResponse.success) {
        const errorMsg = sessionResponse.errorMessage || 'Failed to establish session with server';
        throw new Error(`Session Error: ${errorMsg}`); // Throw to be caught below
      }
      this.logger.info('Session validated/created successfully.');

      // --- Proceed with WebSocket Connection ---
      this.logger.info('Proceeding with WebSocket connection...');
      // wsManager.connect() will update its own state within UnifiedConnectionState
      const wsConnected = await this.wsManager.connect();
      if (!wsConnected) {
          // If WS fails to connect, the error should already be in unifiedState via wsManager
          this.logger.error('WebSocket connection failed after session validation.');
          // No need to throw again, wsManager handled the state update
          return false;
      }
      // If WS connects, SSEManager's listener on WS state change should trigger SSE connect
      return true;

    } catch (error: any) {
      // Catch errors from sessionApi call or wsManager.connect call
      this.logger.error('Connection process failed.', { error: error.message, stack: error.stack });
      const errorMsg = error instanceof Error ? error.message : 'Unknown connection error';
      // Ensure state reflects the failure
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        status: ConnectionStatus.DISCONNECTED,
        error: errorMsg
      });
       this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.DISCONNECTED,
        error: "Connection process failed" // Keep SSE error simple
      });
      // Use injected error handler instance
      this.errorHandler.handleConnectionError(error, ErrorSeverity.HIGH, 'ConnectionManager.connect');
      return false;
    }
  }

  /**
   * Disconnects all underlying connections (WebSocket and SSE).
   * @param reason - A string indicating the reason for disconnection.
   */
  public disconnect(reason: string = 'manual_disconnect'): void {
    if (this.isDisposed) return;
    this.logger.warn(`Disconnect requested via ConnectionManager. Reason: ${reason}`);
    // Disconnecting WebSocket should trigger SSE disconnect via state changes handled in SSEManager
    this.wsManager.disconnect(reason);
    // Explicitly disconnect SSE as well to ensure cleanup, SSEManager handles its state update
    this.sseManager.disconnect(); // Use disconnect() here
    this.logger.warn('Disconnect process completed via ConnectionManager.');
  }

  /**
   * Handles the result of a token refresh attempt. Updates recovery state and handles failures.
   * @param success - Boolean indicating if the token refresh was successful.
   */
  private handleTokenRefresh = (success: boolean): void => {
    if (this.isDisposed) return;
    this.logger.info(`Handling token refresh result in ConnectionManager: success = ${success}`);
    const isAuthenticated = success && this.tokenManager.isAuthenticated();

    // Update recovery manager's view of authentication state
    this.updateRecoveryAuthState(isAuthenticated);

    if (!success) {
      this.logger.error('Authentication token refresh failed.');
      // Use injected error handler
      this.errorHandler.handleAuthError('Session expired or token refresh failed.', ErrorSeverity.HIGH, 'TokenRefresh');
      this.emit('auth_failed', 'Authentication token expired or refresh failed');
      // Consider forcing logout UI flow here if not handled by error handler
    }
  };

  /**
   * Updates the RecoveryManager based on the authentication status and forces disconnect if auth is lost.
   * @param isAuthenticated - Boolean indicating the current authentication status.
   */
  private updateRecoveryAuthState(isAuthenticated: boolean): void {
    if (this.isDisposed) return;
    this.logger.info(`Updating internal recovery auth state: isAuthenticated = ${isAuthenticated}`);
    if (!isAuthenticated) {
      this.logger.warn('Authentication lost, forcing disconnect.');
      this.disconnect('auth_lost'); // Force disconnect if auth is lost
    }
    // Notify recovery manager about auth state change
    this.recoveryManager.updateAuthState(isAuthenticated);
  }

  /**
   * Initiates a connection recovery attempt via the RecoveryManager.
   * @param reason - A string indicating the reason for attempting recovery.
   * @returns A promise resolving to true if recovery is successful, false otherwise.
   */
  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    if (this.isDisposed) {
      this.logger.error("Cannot attempt recovery: ConnectionManager is disposed.");
      return false;
    }
    this.logger.warn(`Connection recovery attempt requested. Reason: ${reason}`);
    return this.recoveryManager.attemptRecovery(reason);
  }

  /**
   * Gets the aggregated current connection state from UnifiedConnectionState.
   * @returns An object representing the overall connection state.
   */
  public getState(): ReturnType<UnifiedConnectionState['getState']> {
    if (this.isDisposed) {
      this.logger.warn("getState called on disposed ConnectionManager. Returning default state.");
      // Create a dummy logger if needed, though `this.logger` should still exist
      const currentLogger = this.logger || Logger.getInstance(); // Fallback if logger could be nullified
      return new UnifiedConnectionState(currentLogger).getState();
    }
    return this.unifiedState.getState();
  }

  // --- Data & Action Methods ---

  /**
   * Retrieves the latest cached exchange data.
   * @returns The exchange data object.
   */
  public getExchangeData(): Record<string, any> {
    if (this.isDisposed) return {};
    return this.dataHandlers.getExchangeData();
  }

  /**
   * Submits a trading order. Requires an active connection.
   * @param order - The order details.
   * @returns A promise resolving to the result of the order submission.
   */
  public async submitOrder(order: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price?: number;
    type: 'MARKET' | 'LIMIT';
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    const state = this.getState();
    if (!state.isConnected) {
      const errorMsg = 'Submit order failed: Not connected to trading servers';
      this.logger.error(errorMsg, { state });
      // Optionally use errorHandler here too?
      // this.errorHandler.handleDataError(errorMsg, ErrorSeverity.LOW, 'SubmitOrderPrecondition');
      return { success: false, error: errorMsg };
    }
    this.logger.info('Submitting order', { symbol: order.symbol, type: order.type, side: order.side });
    // Delegates to dataHandlers, which uses the injected errorHandler for API/data errors
    return this.dataHandlers.submitOrder(order);
  }

  /**
   * Cancels a previously submitted trading order. Requires an active connection.
   * @param orderId - The ID of the order to cancel.
   * @returns A promise resolving to the result of the cancellation attempt.
   */
  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    const state = this.getState();
    if (!state.isConnected) {
      const errorMsg = 'Cancel order failed: Not connected to trading servers';
      this.logger.error(errorMsg, { state });
      // Optionally use errorHandler here too?
      // this.errorHandler.handleDataError(errorMsg, ErrorSeverity.LOW, 'CancelOrderPrecondition');
      return { success: false, error: errorMsg };
    }
    this.logger.info('Cancelling order', { orderId });
    // Delegates to dataHandlers, which uses the injected errorHandler for API/data errors
    return this.dataHandlers.cancelOrder(orderId);
  }

  /**
   * Starts the trading simulator via the API. Requires an active connection.
   * @returns A promise resolving to the result of the start attempt.
   */
  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    const state = this.getState();
    if (!state.isConnected) {
      const errorMsg = 'Start simulator failed: Not connected to trading servers';
      this.logger.error(errorMsg, { state });
      return { success: false, error: errorMsg };
    }
    this.logger.info('Starting simulator');
    return this.simulatorManager.startSimulator();
  }

  /**
   * Stops the trading simulator via the API. Requires an active connection.
   * @returns A promise resolving to the result of the stop attempt.
   */
  public async stopSimulator(): Promise<{ success: boolean; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    const state = this.getState();
    if (!state.isConnected) {
      const errorMsg = 'Stop simulator failed: Not connected to trading servers';
      this.logger.error(errorMsg, { state });
      return { success: false, error: errorMsg };
    }
    this.logger.info('Stopping simulator');
    return this.simulatorManager.stopSimulator();
  }


  // --- Reconnect Methods ---

  /**
   * Explicitly triggers a reconnection attempt (equivalent to attemptRecovery).
   * @returns A promise resolving to true if recovery is successful, false otherwise.
   */
  public async reconnect(): Promise<boolean> {
    if (this.isDisposed) {
      this.logger.error("Cannot reconnect: ConnectionManager is disposed.");
      return false;
    }
    this.logger.warn('Explicit reconnect requested.');
    return this.attemptRecovery('explicit_reconnect_request');
  }

  /**
   * Initiates a manual reconnection attempt, typically triggered by user action.
   * Resets the recovery attempt counter in the process.
   * @returns A promise resolving to true if recovery is successful, false otherwise.
   */
  public async manualReconnect(): Promise<boolean> {
    if (this.isDisposed) {
      this.logger.error("Cannot manual reconnect: ConnectionManager is disposed.");
      return false;
    }
    this.logger.warn('Manual reconnect requested by user.');
    // Signal start of recovery attempt 1 in unified state
    this.unifiedState.updateRecovery(true, 1);
    return this.attemptRecovery('manual_user_request');
  }

  /**
   * Implements the [Symbol.dispose] method for the Disposable interface.
   */
  [Symbol.dispose](): void {
    this.dispose();
  }
}
