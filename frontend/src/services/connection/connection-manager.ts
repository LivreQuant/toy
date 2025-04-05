// src/services/connection/connection-manager.ts

// --- Core Dependencies ---
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { ExchangeDataStream, ExchangeDataOptions } from '../sse/exchange-data-stream';
import { HttpClient } from '../../api/http-client';
import { ConnectionRecoveryInterface } from './connection-recovery-interface';
import { RecoveryManager } from './recovery-manager';
import { WebSocketOptions } from '../websocket/types'; // Import WebSocketOptions
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus,
  ServiceState
} from './unified-connection-state';
import { ConnectionDataHandlers } from './connection-data-handlers';
import { ConnectionSimulatorManager } from './connection-simulator';
import { Logger } from '../../utils/logger';
import { Disposable } from '../../utils/disposable';
import { SessionApi } from '../../api/session';
import { ErrorHandler, ErrorSeverity } from '../../utils/error-handler';
import { toastService } from '../notification/toast-service';

// <<< Import Order types needed for the method signature >>>
import { OrderSide, OrderType } from '../../api/order';

// Update the interface definition to include the new option
export interface ConnectionManagerOptions {
  wsOptions?: WebSocketOptions;
  sseOptions?: ExchangeDataOptions;
}

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
  private isDisposed: boolean = false; // <<< Added dispose flag
  private sessionApi: SessionApi;
  private errorHandler: ErrorHandler;
  private preventAutoConnect: boolean = false; // Add this class property

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
    options: ConnectionManagerOptions = {}
  ) {
    super();

    this.logger = logger;
    this.logger.info('ConnectionManager Initializing...');

    // --- Extract options ---
    const { wsOptions = {}, sseOptions = {} } = options;

    // --- Assign Core Dependencies ---
    this.tokenManager = tokenManager;
    this.errorHandler = new ErrorHandler(this.logger, toastService);

    // Verify authentication before proceeding
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Initializing ConnectionManager without active authentication');
    }

    // --- Instantiate State and Error Handling ---
    this.unifiedState = new UnifiedConnectionState(this.logger);

    // --- Instantiate API Clients ---
    const httpClient = new HttpClient(tokenManager);
    this.sessionApi = new SessionApi(httpClient);

    // --- Configure WebSocketManager with preventAutoConnect ---
    const enhancedWsOptions = {
      ...wsOptions,
      preventAutoConnect: true // Always prevent auto-connect
    };

    // --- Instantiate WebSocketManager ---
    this.wsManager = new WebSocketManager(
      tokenManager,
      this.unifiedState,
      this.logger,
      enhancedWsOptions
    );

    // --- Instantiate SSEManager with preventAutoConnect ---
    const enhancedSseOptions = {
      ...sseOptions,
      preventAutoConnect: true // Always prevent auto-connect
    };

    // --- Instantiate SSE manager ---
    this.sseManager = new ExchangeDataStream(
      tokenManager,
      this.unifiedState,
      this.logger,
      this.errorHandler,
      enhancedSseOptions
    );

    // --- Instantiate Helper Managers ---
    this.dataHandlers = new ConnectionDataHandlers(httpClient, this.errorHandler);
    this.simulatorManager = new ConnectionSimulatorManager(httpClient);
    this.recoveryManager = new RecoveryManager(
      this,
      tokenManager,
      this.unifiedState
    );

    // --- Setup Event Listeners ---
    this.setupEventListeners();
    this.logger.info('ConnectionManager Initialization Complete. Waiting for explicit connect call.');
  }

  /**
   * Sets up internal event listeners for sub-managers and state changes.
   */
  private setupEventListeners(): void {
    this.logger.info('Setting up ConnectionManager event listeners...');

    // --- State Change Listener ---
    this.unifiedState.on('state_change', (state: ReturnType<UnifiedConnectionState['getState']>) => {
      if (this.isDisposed) return; // <<< Check disposed flag
      this.emit('state_change', { current: state });

      // Emit derived events only if state is meaningful (not during/after disposal)
      if (!this.isDisposed) {
          if (state.overallStatus === ConnectionStatus.CONNECTED) {
              this.emit('connected');
          } else if (state.overallStatus === ConnectionStatus.DISCONNECTED) {
              const wsError = state.webSocketState.error;
              const sseError = state.sseState.error;
              const reason = wsError || sseError || 'disconnected';
              this.emit('disconnected', { reason });
          }
      }
    });

    // --- WebSocket State Listener ---
    this.unifiedState.on('websocket_state_change', ({ state }: { state: ServiceState }) => {
        if (this.isDisposed) return; // <<< Check disposed flag
        // Log changes even if disposing, might be useful for debugging shutdown
        this.logger.info(`WebSocket state changed to: ${state.status}`, { error: state.error });
    });

     // --- SSE State Listener ---
     this.unifiedState.on('sse_state_change', ({ state }: { state: ServiceState }) => {
         if (this.isDisposed) return; // <<< Check disposed flag
         this.logger.info(`SSE state changed to: ${state.status}`, { error: state.error });
     });

    // --- Data Event Listeners from SSE Manager ---
    this.sseManager.on('exchange-data', (data: any) => {
      if (this.isDisposed) return; // <<< Check disposed flag
      this.dataHandlers.updateExchangeData(data);
      this.emit('exchange_data', data);
    });

    this.sseManager.on('order-update', (data: any) => {
       if (this.isDisposed) return; // <<< Check disposed flag
       this.logger.info('Received order update via SSE.');
       this.emit('order_update', data);
    });

    // --- Recovery Event Listeners ---
    this.recoveryManager.on('recovery_attempt', (data: any) => {
      if (this.isDisposed) return; // <<< Check disposed flag
      this.logger.warn('Connection recovery attempt started', data);
      this.emit('recovery_attempt', data);
    });
    this.recoveryManager.on('recovery_success', () => {
      if (this.isDisposed) return; // <<< Check disposed flag
      this.logger.info('Connection recovery successful.');
      this.emit('recovery_success');
    });
    this.recoveryManager.on('recovery_failed', (data?: any) => {
      if (this.isDisposed) return; // <<< Check disposed flag
      this.logger.error('Connection recovery failed.', data);
      this.emit('recovery_failed', data);
    });

    // --- Authentication Listener ---
    this.tokenManager.addRefreshListener(this.handleTokenRefresh);

    this.logger.info('ConnectionManager event listeners setup complete.');
  }

  // --- Lifecycle & State Methods ---

  /**
   * Attempts to establish a connection by validating the session and connecting WebSocket.
   * SSE connection will be triggered automatically if WebSocket connects successfully.
   * @returns A promise resolving to true if the connection (including session validation) is successful, false otherwise.
   */
  // Also update the connect() method to verify auth first:
  public async connect(): Promise<boolean> {
    // Check disposed flag
    if (this.isDisposed) {
      this.logger.error("Cannot connect: ConnectionManager is disposed.");
      return false;
    }
    
    // Explicitly verify authentication before proceeding
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.error("Cannot connect: Not authenticated");
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        status: ConnectionStatus.DISCONNECTED,
        error: 'Authentication required'
      });
      return false;
    }
    
     // <<< Check disposed flag after await >>>
    if (this.isDisposed) return false;


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
      this.unifiedState.updateServiceState(ConnectionServiceType.SSE, { status: ConnectionStatus.CONNECTING, error: null });

      const sessionResponse = await this.sessionApi.createSession();

      // <<< Check disposed flag after await >>>
      if (this.isDisposed) {
          this.logger.warn("ConnectionManager disposed during session validation.");
          return false;
      }

      if (!sessionResponse.success) {
        const errorMsg = sessionResponse.errorMessage || 'Failed to establish session with server';
        throw new Error(`Session Error: ${errorMsg}`);
      }
      this.logger.info('Session validated/created successfully.');

      // --- Proceed with WebSocket Connection ---
      this.logger.info('Proceeding with WebSocket connection...');
      const wsConnected = await this.wsManager.connect(); // connect checks disposed flag

       // <<< Check disposed flag after await >>>
      if (this.isDisposed) {
          this.logger.warn("ConnectionManager disposed during WebSocket connection.");
          // Ensure WS is disconnected if it managed to connect partially
          this.wsManager.disconnect("disposed_during_connect");
          return false;
      }

      if (!wsConnected) {
          this.logger.error('WebSocket connection failed after session validation.');
          return false;
      }
      // If WS connects, SSEManager's listener on WS state change should trigger SSE connect
      return true;

    } catch (error: any) {
      // <<< Check disposed flag in error handler >>>
      if (this.isDisposed) {
          this.logger.warn("Connection process failed, but ConnectionManager was disposed. Ignoring error.", { error: error.message });
          return false;
      }
      this.logger.error('Connection process failed.', { error: error.message, stack: error.stack });
      const errorMsg = error instanceof Error ? error.message : 'Unknown connection error';
      // Ensure state reflects the failure
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        status: ConnectionStatus.DISCONNECTED,
        error: errorMsg
      });
       this.unifiedState.updateServiceState(ConnectionServiceType.SSE, {
        status: ConnectionStatus.DISCONNECTED,
        error: "Connection process failed"
      });
      this.errorHandler.handleConnectionError(error, ErrorSeverity.HIGH, 'ConnectionManager.connect');
      return false;
    }
  }

  /**
   * Disconnects all underlying connections (WebSocket and SSE).
   * @param reason - A string indicating the reason for disconnection.
   */
  public disconnect(reason: string = 'manual_disconnect'): void {
    // <<< Allow disconnect even if disposing, but log differently >>>
    if (this.isDisposed && reason !== 'manager_disposed') {
        this.logger.info(`Disconnect (${reason}) called on already disposed ConnectionManager.`);
        return;
    }
    this.logger.warn(`Disconnect requested via ConnectionManager. Reason: ${reason}`);
    // Disconnect WebSocket; SSE should disconnect via its listener
    this.wsManager.disconnect(reason);
    // Explicitly disconnect SSE as well to ensure cleanup in case WS state listener fails
    this.sseManager.disconnect(reason === 'manager_disposed' ? 'dispose' : reason);
    this.logger.warn('Disconnect process completed via ConnectionManager.');
  }

  /**
   * Handles the result of a token refresh attempt. Updates recovery state and handles failures.
   * Bound function reference to preserve 'this'.
   */
  private handleTokenRefresh = (success: boolean): void => {
    if (this.isDisposed) return; // <<< Check disposed flag
    this.logger.info(`Handling token refresh result in ConnectionManager: success = ${success}`);
    const isAuthenticated = success && this.tokenManager.isAuthenticated();

    // Update recovery manager's view of authentication state
    this.updateRecoveryAuthState(isAuthenticated); // Checks disposed flag

    if (!success) {
      this.logger.error('Authentication token refresh failed.');
      this.errorHandler.handleAuthError('Session expired or token refresh failed.', ErrorSeverity.HIGH, 'TokenRefresh');
      this.emit('auth_failed', 'Authentication token expired or refresh failed');
    }
  };

  /**
   * Updates the RecoveryManager based on the authentication status and forces disconnect if auth is lost.
   * @param isAuthenticated - Boolean indicating the current authentication status.
   */
  private updateRecoveryAuthState(isAuthenticated: boolean): void {
    if (this.isDisposed) return; // <<< Check disposed flag
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
    // <<< Check disposed flag early >>>
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
    // <<< Handle disposed state >>>
    if (this.isDisposed) {
      this.logger.warn("getState called on disposed ConnectionManager. Returning default state.");
      // Return a default disconnected state structure
      const defaultState = new UnifiedConnectionState(this.logger || Logger.getInstance());
      const state = defaultState.getState();
      defaultState.dispose(); // Dispose the temporary instance
      return state;
    }
    return this.unifiedState.getState();
  }

  // --- Data & Action Methods ---
  // (submitOrder, cancelOrder, startSimulator, stopSimulator - add isDisposed checks)
  public async submitOrder(order: {
    symbol: string;
    side: OrderSide;
    quantity: number;
    price?: number;
    type: OrderType;
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    const state = this.getState();
    if (!state.isConnected) {
      const errorMsg = 'Submit order failed: Not connected to trading servers';
      this.logger.error(errorMsg, { state });
      return { success: false, error: errorMsg };
    }
    this.logger.info('Submitting order', { symbol: order.symbol, type: order.type, side: order.side });
    return this.dataHandlers.submitOrder(order); // Pass the correctly typed order
  }


  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    // ... rest of existing method
    const state = this.getState();
     if (!state.isConnected) {
       const errorMsg = 'Cancel order failed: Not connected to trading servers';
       this.logger.error(errorMsg, { state });
       return { success: false, error: errorMsg };
     }
     this.logger.info('Cancelling order', { orderId });
     return this.dataHandlers.cancelOrder(orderId);
  }

   public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
     // ... rest of existing method
     const state = this.getState();
     if (!state.isConnected) {
        const errorMsg = 'Start simulator failed: Not connected to trading servers';
        this.logger.error(errorMsg, { state });
        return { success: false, error: errorMsg };
      }
      this.logger.info('Starting simulator');
      return this.simulatorManager.startSimulator();
   }

   public async stopSimulator(): Promise<{ success: boolean; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
     // ... rest of existing method
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
  public async reconnect(): Promise<boolean> {
    if (this.isDisposed) { // <<< Check disposed flag
      this.logger.error("Cannot reconnect: ConnectionManager is disposed.");
      return false;
    }
    this.logger.warn('Explicit reconnect requested.');
    return this.attemptRecovery('explicit_reconnect_request'); // attemptRecovery checks disposed
  }

  public async manualReconnect(): Promise<boolean> {
    if (this.isDisposed) { // <<< Check disposed flag
      this.logger.error("Cannot manual reconnect: ConnectionManager is disposed.");
      return false;
    }
    this.logger.warn('Manual reconnect requested by user.');
    // Signal start of recovery attempt 1 in unified state
    // Check disposed before updating state
    if (!this.isDisposed) {
        this.unifiedState.updateRecovery(true, 1);
    }
    return this.attemptRecovery('manual_user_request'); // attemptRecovery checks disposed
  }

   /**
   * Disposes of the ConnectionManager and all its sub-managers, cleaning up resources.
   * <<< REFACTORED dispose method >>>
   */
  public dispose(): void {
    // *** Check and set disposed flag immediately ***
    if (this.isDisposed) {
      this.logger.warn('ConnectionManager already disposed.');
      return;
    }
    this.logger.warn('Disposing ConnectionManager...');
    this.isDisposed = true; // Set flag early

    // --- Unsubscribe from external events ---
    if (this.tokenManager) {
      try {
        // Use the stored bound function reference for removal
        this.tokenManager.removeRefreshListener(this.handleTokenRefresh);
      } catch (error) {
        this.logger.error('Error removing token refresh listener during dispose', { error });
      }
    }
    // No direct subscription to unifiedState in this class

    // --- Helper to safely call dispose methods ---
    const tryDispose = (manager: any, managerName: string) => {
      if (!manager) return;
      this.logger.info(`Attempting to dispose ${managerName}...`);
      try {
        let disposed = false;
        if (manager && typeof manager[Symbol.dispose] === 'function') {
          manager[Symbol.dispose]();
          disposed = true;
        } else if (manager && typeof manager.dispose === 'function') {
          manager.dispose();
          disposed = true;
        }
        if(disposed) this.logger.info(`${managerName} disposed successfully.`);
        else this.logger.warn(`${managerName} does not seem to have a standard dispose method.`);

      } catch (error) {
        this.logger.error(`Error during ${managerName} disposal`, { error });
      }
    };

    // --- Dispose managers in a safe order ---
    // Disconnect connections explicitly first via disconnect()
    this.disconnect('manager_disposed'); // Calls disconnect on wsManager and sseManager

    // Now dispose the managers themselves
    tryDispose(this.recoveryManager, 'RecoveryManager');
    tryDispose(this.sseManager, 'ExchangeDataStream/SSEManager'); // Dispose after disconnect call
    tryDispose(this.wsManager, 'WebSocketManager'); // Dispose after disconnect call
    tryDispose(this.unifiedState, 'UnifiedConnectionState');
    // Dispose others if they implement Disposable and hold resources/timers
    // tryDispose(this.dataHandlers, 'ConnectionDataHandlers');
    // tryDispose(this.simulatorManager, 'ConnectionSimulatorManager');
    // tryDispose(this.errorHandler, 'ErrorHandler');


    // --- Remove own listeners last ---
    this.removeAllListeners(); // From EventEmitter base

    this.logger.warn('ConnectionManager disposed.');
  }


  /**
   * Implements the [Symbol.dispose] method for the Disposable interface.
   */
  [Symbol.dispose](): void {
    this.dispose();
  }
}