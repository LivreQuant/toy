// src/services/connection/connection-manager.ts
import { Subscription } from 'rxjs';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager, WebSocketEvents } from '../websocket/websocket-manager';
import { HttpClient } from '../../api/http-client';
import { ConnectionResilienceManager } from './connection-resilience-manager';
import { WebSocketOptions } from '../websocket/types';
import { appState, ConnectionStatus, ConnectionQuality, AppState } from '../state/app-state.service';
import { ConnectionDataHandlers } from './connection-data-handlers';
import { ConnectionSimulatorManager } from './connection-simulator';
import { Disposable } from '../../utils/disposable';
import { SessionApi } from '../../api/session';
import { AppErrorHandler } from '../../utils/app-error-handler';
import { ErrorSeverity } from '../../utils/error-handler';
// Import specific request/response types needed for method signatures
import { OrderSide, OrderType, SubmitOrderRequest, SubmitOrderResponse } from '../../api/order';
import { SimulatorStatusResponse } from '../../api/simulator'; // Import simulator response type
import { EnhancedLogger } from '../../utils/enhanced-logger';
import { getLogger } from '../../boot/logging';
import { TypedEventEmitter } from '../../utils/typed-event-emitter';

export interface ConnectionManagerEvents {
  auth_failed: { reason: string };
}

export interface ConnectionDesiredState {
  connected: boolean;
  simulatorRunning: boolean;
}

export interface ConnectionManagerOptions {
  wsOptions?: WebSocketOptions;
  resilience?: {
    initialDelayMs?: number;
    maxDelayMs?: number;
    maxAttempts?: number;
    suspensionTimeoutMs?: number;
    failureThreshold?: number;
    jitterFactor?: number;
  };
}

// Define the specific return types for the public methods
// Matches SubmitOrderResponse but makes orderId optional for the return structure
type SubmitOrderResult = { success: boolean; orderId?: string; error?: string };
type CancelOrderResult = { success: boolean; error?: string };
// Matches SimulatorStatusResponse but makes status/error optional for the return structure
type SimulatorActionResult = { success: boolean; status?: string; error?: string };


export class ConnectionManager extends TypedEventEmitter<ConnectionManagerEvents> implements Disposable {
  protected logger: EnhancedLogger; // Ensure logger is accessible
  private dataHandlers: ConnectionDataHandlers;
  private simulatorManager: ConnectionSimulatorManager;
  private resilienceManager: ConnectionResilienceManager;
  private wsManager: WebSocketManager;
  private tokenManager: TokenManager;
  private sessionApi: SessionApi;
  private httpClient: HttpClient;
  private subscriptions = new Subscription();
  public desiredState: ConnectionDesiredState = { connected: false, simulatorRunning: false };

  constructor(
    tokenManager: TokenManager,
    options: ConnectionManagerOptions = {}
  ) {
    const loggerInstance = getLogger('ConnectionManager');
    super(loggerInstance);
    this.logger = loggerInstance; // Assign logger explicitly if needed locally

    this.logger.info('ConnectionManager initializing...', { options });

    this.tokenManager = tokenManager;

    const initialAuthState = appState.getState().auth;
    if (!initialAuthState.isAuthenticated && !initialAuthState.isAuthLoading) {
      this.logger.warn('Initializing ConnectionManager without active authentication');
    } else if (initialAuthState.isAuthenticated) {
        this.logger.info('Initializing ConnectionManager with potentially existing authentication');
    }

    this.httpClient = new HttpClient(tokenManager);
    this.sessionApi = new SessionApi(this.httpClient);
    this.dataHandlers = new ConnectionDataHandlers(this.httpClient);
    this.simulatorManager = new ConnectionSimulatorManager(this.httpClient);
    this.wsManager = new WebSocketManager(
      tokenManager,
      {
        ...options.wsOptions,
        preventAutoConnect: true
      }
    );

    const resilienceOptions = options.resilience ? {
        initialDelayMs: options.resilience.initialDelayMs,
        maxDelayMs: options.resilience.maxDelayMs,
        maxAttempts: options.resilience.maxAttempts,
        suspensionTimeoutMs: options.resilience.suspensionTimeoutMs,
        failureThreshold: options.resilience.failureThreshold,
        jitterFactor: options.resilience.jitterFactor
    } : undefined;

    this.resilienceManager = new ConnectionResilienceManager(
      tokenManager,
      this.logger,
      resilienceOptions
    );

    this.setupEventListeners();

    this.logger.info('ConnectionManager initialized');
  }

  // --- Private Methods ---
  // ... (setupEventListeners, syncConnectionState, syncSimulatorState, connect, disconnect, attemptRecovery)
  // No type changes needed in the previous methods from the last update

  private setupEventListeners(): void {
    // Use 'this.isDisposed' (inherited getter)
    this.logger.info('Setting up ConnectionManager event listeners');

    this.subscriptions.add(
        this.wsManager.getConnectionStatus().subscribe(status => {
            if (this.isDisposed) return; // Use inherited getter
             this.logger.debug(`WebSocketManager status changed: ${status}`);

            if (status === ConnectionStatus.DISCONNECTED && this.desiredState.connected) {
               this.logger.warn('WebSocket disconnected unexpectedly while desired state is connected. Attempting recovery.');
               this.attemptRecovery('ws_unexpected_disconnect');
            } else if (status === ConnectionStatus.CONNECTED) {
                this.resilienceManager.reset();
                 if (appState.getState().connection.webSocketStatus !== ConnectionStatus.CONNECTED) {
                     appState.updateConnectionState({
                         webSocketStatus: ConnectionStatus.CONNECTED,
                         isRecovering: false,
                         recoveryAttempt: 0,
                         lastConnectionError: null
                     });
                 }
                this.syncSimulatorState();
            }
        })
    );

    this.wsManager.subscribe('heartbeat', (hbData) => {
        if (this.isDisposed) return; // Use inherited getter
        const quality = appState.calculateConnectionQuality(hbData.latency);
        appState.updateConnectionState({
            lastHeartbeatTime: Date.now(),
            heartbeatLatency: hbData.latency >= 0 ? hbData.latency : null,
            quality: quality,
            ...(hbData.simulatorStatus && { simulatorStatus: hbData.simulatorStatus })
        });
    });

    this.wsManager.subscribe('exchange_data', (data) => {
        if (this.isDisposed) return; // Use inherited getter
        appState.updateExchangeSymbols(data);
    });
    this.wsManager.subscribe('portfolio_data', (data) => {
        if (this.isDisposed) return; // Use inherited getter
        appState.updatePortfolioState({
           cash: data.cash,
           positions: data.positions
        });
    });
     this.wsManager.subscribe('order_update', (data) => {
        if (this.isDisposed) return; // Use inherited getter
        appState.updatePortfolioOrder(data);
     });

     this.wsManager.subscribe('session_invalidated', (data) => {
        if (this.isDisposed) return; // Use inherited getter
        this.logger.error(`Session invalidated by server. Reason: ${data.reason}. Forcing disconnect and logout.`);
        AppErrorHandler.handleAuthError(
            `Session invalidated: ${data.reason}`,
            ErrorSeverity.HIGH,
            'WebSocketSessionInvalid'
        );
        this.setDesiredState({ connected: false });
        this.emit('auth_failed', { reason: `Session invalidated: ${data.reason}` });
     });

    this.resilienceManager.subscribe('reconnect_scheduled', (data: any) => {
        if (this.isDisposed) return; // Use inherited getter
        this.logger.info(`Resilience: Reconnection scheduled: attempt ${data.attempt}/${data.maxAttempts} in ${data.delay}ms`);
        appState.updateConnectionState({ isRecovering: true, recoveryAttempt: data.attempt });
    });
    this.resilienceManager.subscribe('reconnect_success', () => {
         if (this.isDisposed) return; // Use inherited getter
         this.logger.info('Resilience: Connection recovery successful');
    });
    this.resilienceManager.subscribe('reconnect_failure', (data: any) => {
         if (this.isDisposed) return; // Use inherited getter
         this.logger.warn(`Resilience: Reconnection attempt ${data.attempt} failed`);
         appState.updateConnectionState({
            lastConnectionError: `Reconnection attempt ${data.attempt} failed.`
         });
    });
     this.resilienceManager.subscribe('max_attempts_reached', (data: any) => {
         if (this.isDisposed) return; // Use inherited getter
         const errorMsg = `Failed to reconnect after ${data.maxAttempts} attempts. Please check your connection or try again later.`;
         this.logger.error(`Resilience: ${errorMsg}`);
         appState.updateConnectionState({
             isRecovering: false,
             lastConnectionError: `Failed to reconnect after ${data.maxAttempts} attempts.`,
             webSocketStatus: ConnectionStatus.DISCONNECTED
         });
         AppErrorHandler.handleConnectionError(
            errorMsg,
            ErrorSeverity.HIGH,
            'ConnectionResilienceMaxAttempts'
         );
    });
    this.resilienceManager.subscribe('suspended', (data: any) => {
        if (this.isDisposed) return; // Use inherited getter
        const suspensionDuration = this.resilienceManager.options.suspensionTimeoutMs / 1000;
        const errorMsg = `Connection attempts suspended for ${suspensionDuration}s due to ${data.failureCount} failures.`;
        this.logger.error(`Resilience: ${errorMsg}`);
         appState.updateConnectionState({
            isRecovering: false,
            lastConnectionError: `Connection attempts suspended due to repeated failures.`,
             webSocketStatus: ConnectionStatus.DISCONNECTED
         });
          AppErrorHandler.handleConnectionError(errorMsg, ErrorSeverity.MEDIUM, 'ConnectionSuspended');
    });
    this.resilienceManager.subscribe('resumed', () => {
         if (this.isDisposed) return; // Use inherited getter
         this.logger.info(`Resilience: Connection attempts can resume.`);
         appState.updateConnectionState({ lastConnectionError: null });
         this.syncConnectionState();
    });


    this.subscriptions.add(
        appState.select(state => state.auth).subscribe(authState => {
            if (this.isDisposed) return; // Use inherited getter
             this.logger.debug(`Auth state changed: isAuthenticated=${authState.isAuthenticated}, isAuthLoading=${authState.isAuthLoading}`);
            this.resilienceManager.updateAuthState(authState.isAuthenticated);

            if (!authState.isAuthLoading) {
                if (authState.isAuthenticated) {
                    this.syncConnectionState();
                } else {
                    const currentState = appState.getState().connection;
                    if (currentState.webSocketStatus !== ConnectionStatus.DISCONNECTED || currentState.isRecovering) {
                        this.logger.info('Authentication lost or absent, forcing disconnect.');
                        this.setDesiredState({ connected: false });
                    }
                }
            }
        })
    );

    this.logger.info('ConnectionManager event listeners setup complete');
  }

  public setDesiredState(state: Partial<ConnectionDesiredState>): void {
    if (this.isDisposed) { // Use inherited getter
      this.logger.error('Cannot set desired state: ConnectionManager is disposed');
      return;
    }
    const changed = Object.keys(state).some(
        key => this.desiredState[key as keyof ConnectionDesiredState] !== state[key as keyof ConnectionDesiredState]
    );
    if (!changed) {
        this.logger.debug('Desired state unchanged, skipping sync.');
        return;
    }
    const oldState = { ...this.desiredState };
    this.desiredState = { ...this.desiredState, ...state };
    this.logger.info('Desired state updated', { oldState, newState: this.desiredState });
    this.syncConnectionState();
    this.syncSimulatorState();
  }

  private syncConnectionState(): void {
    if (this.isDisposed) return; // Use inherited getter
    const currentAuthState = appState.getState().auth;
    if (currentAuthState.isAuthLoading) {
        this.logger.debug('Sync connection state skipped: Authentication is loading.');
        return;
    }
     if (this.resilienceManager.getState().state === 'suspended') {
        this.logger.debug(`Sync connection state skipped: Suspended (State: ${this.resilienceManager.getState().state})`);
        return;
    }

    const currentConnState = appState.getState().connection;
    const isConnected = currentConnState.webSocketStatus === ConnectionStatus.CONNECTED;
    const isConnecting = currentConnState.webSocketStatus === ConnectionStatus.CONNECTING;
    const isRecovering = currentConnState.isRecovering;

    if (this.desiredState.connected && !currentAuthState.isAuthenticated) {
        this.logger.warn('Sync connection state: Cannot connect, user is not authenticated.');
        if (isConnected || isConnecting || isRecovering) {
           this.disconnect('not_authenticated');
        }
        return;
    }

    if (this.desiredState.connected && !isConnected && !isConnecting && !isRecovering) {
      this.logger.info('Syncing connection state: attempting to connect (auth confirmed)');
      this.connect().catch(err => {
        this.logger.error('Connect call during state sync returned an error', { error: err instanceof Error ? err.message : String(err) });
      });
    } else if (!this.desiredState.connected && (isConnected || isConnecting || isRecovering)) {
      this.logger.info('Syncing connection state: disconnecting');
      this.disconnect('desired_state_change');
    } else {
         this.logger.debug('Sync connection state: No action needed.', { desired: this.desiredState.connected, isAuthenticated: currentAuthState.isAuthenticated, isConnected, isConnecting, isRecovering });
    }
  }

  private async syncSimulatorState(): Promise<void> {
     if (this.isDisposed) return; // Use inherited getter
     const currentConnState = appState.getState().connection;
     const isConnected = currentConnState.webSocketStatus === ConnectionStatus.CONNECTED;
     if (!isConnected) {
         this.logger.debug('Sync simulator state skipped: Not connected.');
         return;
     }
     const currentSimStatus = currentConnState.simulatorStatus;
     const isRunning = currentSimStatus === 'RUNNING';
     const isBusy = currentSimStatus === 'STARTING' || currentSimStatus === 'STOPPING';
     if (this.desiredState.simulatorRunning && !isRunning && !isBusy) {
         this.logger.info('Syncing simulator state: attempting to start simulator');
         await this.startSimulator();
     } else if (!this.desiredState.simulatorRunning && isRunning && !isBusy) {
         this.logger.info('Syncing simulator state: stopping simulator');
         await this.stopSimulator();
     } else {
         this.logger.debug('Sync simulator state: No action needed.', { desired: this.desiredState.simulatorRunning, currentStatus: currentSimStatus });
     }
  }

  public async connect(): Promise<boolean> {
     if (this.isDisposed) return false; // Use inherited getter
     const currentAuthState = appState.getState().auth;
     if (currentAuthState.isAuthLoading) {
         this.logger.warn('Connect call ignored: Authentication is loading.');
         return false;
     }
     if (!currentAuthState.isAuthenticated) {
         this.logger.error('Connect call failed: Not authenticated.');
         appState.updateConnectionState({
             webSocketStatus: ConnectionStatus.DISCONNECTED,
             lastConnectionError: 'Authentication required',
             isRecovering: false
         });
         return false;
     }

     const currentStatus = appState.getState().connection.webSocketStatus;
     if (currentStatus === ConnectionStatus.CONNECTING || currentStatus === ConnectionStatus.CONNECTED) {
         this.logger.warn(`Connect call ignored: WebSocket status is already ${currentStatus}`);
         return currentStatus === ConnectionStatus.CONNECTED;
     }
     if (appState.getState().connection.isRecovering || this.resilienceManager.getState().state === 'suspended') {
         this.logger.warn(`Connect call ignored: Currently recovering or suspended.`);
         return false;
     }


    return this.logger.trackTime('connect', async () => {
      if (this.isDisposed) return false; // Use inherited getter

      if (!this.tokenManager.isAuthenticated()) {
        this.logger.error('Cannot connect: Not authenticated (re-check failed)');
        appState.updateConnectionState({ webSocketStatus: ConnectionStatus.DISCONNECTED, lastConnectionError: 'Authentication required' });
        return false;
      }

      this.logger.info('Attempting to establish connection...');
      appState.updateConnectionState({
          webSocketStatus: ConnectionStatus.CONNECTING,
          lastConnectionError: null,
          isRecovering: false
      });

      try {
        this.logger.info('Validating session with backend...');
        const sessionResponse = await this.sessionApi.createSession();
        if (this.isDisposed) return false; // Use inherited getter
        if (!sessionResponse.success) {
          throw new Error(`Session Error: ${sessionResponse.errorMessage || 'Failed to establish session'}`);
        }
        this.logger.info('Session validated successfully.');

        this.logger.info('Connecting WebSocket...');
        const wsConnected = await this.wsManager.connect();
        if (this.isDisposed) { // Use inherited getter
             if (wsConnected) this.wsManager.disconnect('disposed_during_connect');
            return false;
        }

        if (!wsConnected) {
           this.logger.error('WebSocket connection failed after session validation.');
            if (!appState.getState().connection.lastConnectionError) {
                appState.updateConnectionState({ lastConnectionError: 'WebSocket failed to connect' });
            }
           this.resilienceManager.recordFailure('WebSocket failed to connect');
           this.attemptRecovery('ws_connect_failed');
           return false;
        }

        this.logger.info('Connection established successfully.');
        return true;

      } catch (error: any) {
        if (this.isDisposed) return false; // Use inherited getter
        const errorMessage = error instanceof Error ? error.message : String(error);
        this.logger.error('Connection process failed', { error: errorMessage });

        appState.updateConnectionState({
          webSocketStatus: ConnectionStatus.DISCONNECTED,
          isRecovering: false,
          lastConnectionError: errorMessage
        });

        this.resilienceManager.recordFailure(errorMessage);
        this.attemptRecovery('initial_connect_failed');

        AppErrorHandler.handleConnectionError(errorMessage, ErrorSeverity.HIGH, 'ConnectionManager.connect');
        return false;
      }
    });
  }

  public disconnect(reason: string = 'manual_disconnect'): void {
    if (this.isDisposed && reason !== 'manager_disposed') { // Use inherited getter
      this.logger.info(`Disconnect called on disposed ConnectionManager. Reason: ${reason}`);
      return;
    }
     const currentState = appState.getState().connection;
     const wasConnectedOrConnecting = currentState.webSocketStatus !== ConnectionStatus.DISCONNECTED || currentState.isRecovering;
     if (!wasConnectedOrConnecting) {
         this.logger.debug(`Disconnect call ignored: Already disconnected. Reason: ${reason}`);
         return;
     }
     this.logger.warn(`Disconnecting. Reason: ${reason}`);
     this.resilienceManager.reset();
     this.wsManager.disconnect(reason);
     appState.updateConnectionState({
         webSocketStatus: ConnectionStatus.DISCONNECTED,
         isRecovering: false,
         quality: ConnectionQuality.UNKNOWN,
         heartbeatLatency: null,
         lastHeartbeatTime: undefined,
         lastConnectionError: `Disconnected: ${reason}`,
         ...(currentState.simulatorStatus === 'RUNNING' && { simulatorStatus: 'UNKNOWN' })
     });
  }

  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
     if (this.isDisposed) return false; // Use inherited getter
     const currentAuthState = appState.getState().auth;
     if (currentAuthState.isAuthLoading) {
         this.logger.warn(`Recovery attempt ignored: Authentication is loading. Reason: ${reason}`);
         return false;
     }
      if (!currentAuthState.isAuthenticated) {
          this.logger.warn(`Recovery attempt ignored: Not authenticated. Reason: ${reason}`);
          return false;
      }
     const resilienceState = this.resilienceManager.getState();
     if (appState.getState().connection.isRecovering || resilienceState.state === 'suspended') {
        this.logger.warn(`Recovery attempt ignored: Already recovering or suspended. Reason: ${reason}`);
        return false;
     }
     this.logger.warn(`Connection recovery requested. Reason: ${reason}`);
     appState.updateConnectionState({ isRecovering: true, recoveryAttempt: 1 });
     this.resilienceManager.attemptReconnection(() => this.connect())
         .then(initiated => {
             if (!initiated && !this.isDisposed) { // Use inherited getter
                 this.logger.warn("Recovery process could not be initiated.");
                  if(appState.getState().connection.isRecovering) {
                     appState.updateConnectionState({ isRecovering: false, recoveryAttempt: 0 });
                  }
             }
         });
     return true;
  }

  // --- Public Actions ---

  /**
   * Submits a trading order.
   * FIX: Added explicit parameter type and return type.
   */
  public async submitOrder(
    // FIX: Add type annotation for the 'order' parameter
    order: {
      symbol: string;
      side: OrderSide;
      quantity: number;
      price?: number;
      type: OrderType;
    }
    // FIX: Add explicit Promise return type annotation
  ): Promise<SubmitOrderResult> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    const state = appState.getState().connection;
    if (state.webSocketStatus !== ConnectionStatus.CONNECTED) {
      const errorMsg = 'Submit order failed: Not connected to trading service';
      AppErrorHandler.handleGenericError(errorMsg, ErrorSeverity.MEDIUM, 'SubmitOrderCheck');
      return { success: false, error: errorMsg };
    }
     if (state.simulatorStatus !== 'RUNNING') {
       const errorMsg = 'Submit order failed: Simulator not running';
       AppErrorHandler.handleGenericError(errorMsg, ErrorSeverity.MEDIUM, 'SubmitOrderCheck');
       return { success: false, error: errorMsg };
     }
    // FIX: Now TypeScript knows the properties of 'order' exist
    this.logger.info('Submitting order', { symbol: order.symbol, type: order.type, side: order.side });
    // FIX: Now TypeScript knows 'order' matches the expected parameter type
    return this.dataHandlers.submitOrder(order);
  }

  /**
   * Cancels a trading order.
   * FIX: Added explicit return type.
   */
  public async cancelOrder(orderId: string): Promise<CancelOrderResult> { // FIX: Add return type
      if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
      const state = appState.getState().connection;
      if (state.webSocketStatus !== ConnectionStatus.CONNECTED) {
         const errorMsg = 'Cancel order failed: Not connected to trading service';
         AppErrorHandler.handleGenericError(errorMsg, ErrorSeverity.MEDIUM, 'CancelOrderCheck');
         return { success: false, error: errorMsg };
      }
       if (state.simulatorStatus !== 'RUNNING') {
          const errorMsg = 'Cancel order failed: Simulator not running';
          AppErrorHandler.handleGenericError(errorMsg, ErrorSeverity.MEDIUM, 'CancelOrderCheck');
          return { success: false, error: errorMsg };
       }
      this.logger.info('Cancelling order', { orderId });
      return this.dataHandlers.cancelOrder(orderId);
  }

  /**
   * Starts the simulator.
   * FIX: Added explicit return type.
   */
  public async startSimulator(): Promise<SimulatorActionResult> { // FIX: Add return type
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
     this.desiredState.simulatorRunning = true;
     const state = appState.getState().connection;
     if (state.webSocketStatus !== ConnectionStatus.CONNECTED) {
       const errorMsg = 'Start simulator failed: Not connected';
       return { success: false, error: errorMsg }; // Return matches SimulatorActionResult
     }
     if (state.simulatorStatus === 'RUNNING' || state.simulatorStatus === 'STARTING') {
        this.logger.warn(`Start simulator ignored: Already ${state.simulatorStatus}`);
        return { success: true, status: state.simulatorStatus }; // Return matches SimulatorActionResult
     }

     this.logger.info('Starting simulator...');
     appState.updateConnectionState({ simulatorStatus: 'STARTING' });
     try {
         // simulatorManager methods already return SimulatorStatusResponse
         const result: SimulatorStatusResponse = await this.simulatorManager.startSimulator();
         if (this.isDisposed) return { success: false, error: 'Disposed during start' };
         appState.updateConnectionState({
             simulatorStatus: result.success ? (result.status || 'RUNNING') : 'ERROR',
             lastConnectionError: result.success ? null : (result.errorMessage || 'Failed to start simulator')
         });
         if (!result.success) {
             this.desiredState.simulatorRunning = false;
             AppErrorHandler.handleGenericError(result.errorMessage || 'Failed to start simulator', ErrorSeverity.MEDIUM, 'StartSimulator');
         }
         // Adapt the API response to the SimulatorActionResult structure
         return { success: result.success, status: result.status, error: result.errorMessage };
     } catch (error: any) {
         if (this.isDisposed) return { success: false, error: 'Disposed during start exception' };
          const errorMsg = error instanceof Error ? error.message : String(error);
          this.logger.error('Error starting simulator', { error: errorMsg });
          appState.updateConnectionState({ simulatorStatus: 'ERROR', lastConnectionError: errorMsg });
          this.desiredState.simulatorRunning = false;
          AppErrorHandler.handleGenericError(errorMsg, ErrorSeverity.HIGH, 'StartSimulatorException');
          // Return matches SimulatorActionResult structure
          return { success: false, error: errorMsg };
     }
  }

  /**
   * Stops the simulator.
   * FIX: Added explicit return type.
   */
  public async stopSimulator(): Promise<SimulatorActionResult> { // FIX: Add return type
     if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
      this.desiredState.simulatorRunning = false;
      const state = appState.getState().connection;
      if (state.webSocketStatus !== ConnectionStatus.CONNECTED) {
        const errorMsg = 'Stop simulator failed: Not connected';
        return { success: false, error: errorMsg }; // Return matches SimulatorActionResult
      }
       if (state.simulatorStatus !== 'RUNNING' && state.simulatorStatus !== 'STARTING') {
           this.logger.warn(`Stop simulator ignored: Not running or starting (status: ${state.simulatorStatus})`);
           return { success: true, status: state.simulatorStatus }; // Return matches SimulatorActionResult
       }

      this.logger.info('Stopping simulator...');
      appState.updateConnectionState({ simulatorStatus: 'STOPPING' });
      try {
          const result: SimulatorStatusResponse = await this.simulatorManager.stopSimulator();
          if (this.isDisposed) return { success: false, error: 'Disposed during stop' };
          const simStatus = result.success ? 'STOPPED' : 'ERROR';
          const errorMsg = result.success ? null : (result.errorMessage || 'Failed to stop simulator');
          appState.updateConnectionState({ simulatorStatus: simStatus, lastConnectionError: errorMsg });
          if (!result.success) {
               AppErrorHandler.handleGenericError(errorMsg || 'Failed to stop simulator', ErrorSeverity.MEDIUM, 'StopSimulator');
          }
          // Adapt the API response to the SimulatorActionResult structure
          return { success: result.success, status: result.status, error: result.errorMessage };
      } catch (error: any) {
          if (this.isDisposed) return { success: false, error: 'Disposed during stop exception' };
           const errorMsg = error instanceof Error ? error.message : String(error);
           this.logger.error('Error stopping simulator', { error: errorMsg });
           appState.updateConnectionState({ simulatorStatus: 'ERROR', lastConnectionError: errorMsg });
           AppErrorHandler.handleGenericError(errorMsg, ErrorSeverity.HIGH, 'StopSimulatorException');
            // Return matches SimulatorActionResult structure
           return { success: false, error: errorMsg };
      }
  }

  /**
   * Initiates a manual reconnection attempt.
   */
  public manualReconnect(): void {
     if (this.isDisposed) return;
     this.logger.warn('Manual reconnect triggered');
     this.setDesiredState({ connected: true });
     this.attemptRecovery('manual_user_request');
  }


  public override dispose(): void {
       if (this.isDisposed) return;
       this.logger.warn('Disposing ConnectionManager');
       this.disconnect('manager_disposed');
       if (this.resilienceManager && typeof this.resilienceManager.dispose === 'function') {
           this.resilienceManager.dispose();
       }
       if (this.wsManager && typeof this.wsManager.dispose === 'function') {
           this.wsManager.dispose();
       }
       this.subscriptions.unsubscribe();
       super.dispose();
       this.logger.info('ConnectionManager disposed');
   }


  [Symbol.dispose](): void {
    this.dispose();
  }
}