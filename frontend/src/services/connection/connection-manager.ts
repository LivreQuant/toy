// src/services/connection/connection-manager.ts
import { Subscription } from 'rxjs';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager, WebSocketEvents } from '../websocket/websocket-manager';
import { HttpClient } from '../../api/http-client';
import { ConnectionResilienceManager } from './connection-resilience-manager';
import { WebSocketOptions } from '../websocket/types';
import {
  appState,
  AppStateService,
  ConnectionStatus,
  ConnectionQuality
} from '../state/app-state.service';
import { ConnectionDataHandlers } from './connection-data-handlers';
import { ConnectionSimulatorManager } from './connection-simulator';
import { Disposable } from '../../utils/disposable';
import { SessionApi } from '../../api/session';
import { AppErrorHandler } from '../../utils/app-error-handler';
import { ErrorSeverity } from '../../utils/error-handler';
import { OrderSide, OrderType } from '../../api/order';
import { getLogger } from '../../boot/logging';
import { TypedEventEmitter } from '../../utils/typed-event-emitter';

// Define specific (non-state) event types for ConnectionManager consumers
export interface ConnectionManagerEvents {
  auth_failed: { reason: string };
  // Add other specific events if needed (e.g., 'order_submitted', 'simulator_started')
}


// Define the desired connection state
export interface ConnectionDesiredState {
  connected: boolean;
  simulatorRunning: boolean;
}

// Options for the ConnectionManager
export interface ConnectionManagerOptions {
  wsOptions?: WebSocketOptions;
  resilience?: {
    initialDelayMs?: number;
    maxDelayMs?: number;
    maxAttempts?: number;
    // removed resetTimeoutMs - not used by resilience manager
    suspensionTimeoutMs?: number; // Correct option name
    failureThreshold?: number;
    jitterFactor?: number; // Added from resilience options
  };
}


export class ConnectionManager extends TypedEventEmitter<ConnectionManagerEvents> implements Disposable {
  private dataHandlers: ConnectionDataHandlers;
  private simulatorManager: ConnectionSimulatorManager;
  private resilienceManager: ConnectionResilienceManager;
  private wsManager: WebSocketManager;
  private tokenManager: TokenManager;
  private sessionApi: SessionApi;
  private httpClient: HttpClient;

  private logger = getLogger('ConnectionManager');
  private isDisposed: boolean = false;
  private subscriptions = new Subscription();

  public desiredState: ConnectionDesiredState = {
    connected: false,
    simulatorRunning: false
  };

  constructor(
    tokenManager: TokenManager,
    options: ConnectionManagerOptions = {}
  ) {
    super('ConnectionManager');
    this.logger.info('ConnectionManager initializing...', { options });

    this.tokenManager = tokenManager;

    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Initializing ConnectionManager without active authentication');
      appState.updateAuthState({ isAuthenticated: false, isAuthLoading: false });
    } else {
        appState.updateAuthState({ isAuthenticated: true, isAuthLoading: false, userId: tokenManager.getUserId() });
    }

    this.httpClient = new HttpClient(tokenManager);
    this.sessionApi = new SessionApi(this.httpClient);

    // FIX: Remove second argument from ConnectionDataHandlers constructor
    this.dataHandlers = new ConnectionDataHandlers(this.httpClient);
    this.simulatorManager = new ConnectionSimulatorManager(this.httpClient);

    this.wsManager = new WebSocketManager(
      tokenManager,
      {
        ...options.wsOptions,
        preventAutoConnect: true
      }
    );

    // Ensure options passed to ConnectionResilienceManager match its definition
    const resilienceOptions = options.resilience ? {
        initialDelayMs: options.resilience.initialDelayMs,
        maxDelayMs: options.resilience.maxDelayMs,
        maxAttempts: options.resilience.maxAttempts,
        suspensionTimeoutMs: options.resilience.suspensionTimeoutMs, // Use correct name
        failureThreshold: options.resilience.failureThreshold,
        jitterFactor: options.resilience.jitterFactor
    } : undefined;

    this.resilienceManager = new ConnectionResilienceManager(
      tokenManager,
      this.logger.createChild('Resilience'),
      resilienceOptions // Pass filtered/correct options
    );

    this.setupEventListeners();

    this.logger.info('ConnectionManager initialized');
  }

  /**
   * Sets up event listeners for underlying services and auth state.
   */
  private setupEventListeners(): void {
    this.logger.info('Setting up ConnectionManager event listeners');

    // --- WebSocketManager Listeners ---
    this.subscriptions.add(
        this.wsManager.getConnectionStatus().subscribe(status => {
            if (this.isDisposed) return;
             this.logger.debug(`WebSocketManager status changed: ${status}`);
            // Update central state based on WS status
            appState.updateConnectionState({ webSocketStatus: status });

            if (status === ConnectionStatus.DISCONNECTED && this.desiredState.connected) {
               this.logger.warn('WebSocket disconnected unexpectedly while desired state is connected. Attempting recovery.');
               this.attemptRecovery('ws_unexpected_disconnect');
            } else if (status === ConnectionStatus.CONNECTED) {
                this.resilienceManager.reset(); // Reset resilience on successful connect
            }
        })
    );

    this.wsManager.subscribe('heartbeat', (hbData) => {
        if (this.isDisposed) return;
        const quality = appState.calculateConnectionQuality(hbData.latency);
        appState.updateConnectionState({
            lastHeartbeatTime: Date.now(),
            heartbeatLatency: hbData.latency >= 0 ? hbData.latency : null,
            quality: quality,
            ...(hbData.simulatorStatus && { simulatorStatus: hbData.simulatorStatus })
        });
    });

    this.wsManager.subscribe('exchange_data', (data) => {
        if (this.isDisposed) return;
        appState.updateExchangeSymbols(data);
    });
    this.wsManager.subscribe('portfolio_data', (data) => {
        if (this.isDisposed) return;
        appState.updatePortfolioState({
           cash: data.cash,
           positions: data.positions
        });
    });
     this.wsManager.subscribe('order_update', (data) => {
        if (this.isDisposed) return;
        appState.updatePortfolioOrder(data);
     });

     this.wsManager.subscribe('session_invalidated', (data) => {
        if (this.isDisposed) return;
        this.logger.error(`Session invalidated by server. Reason: ${data.reason}. Forcing disconnect and logout.`);
        AppErrorHandler.handleAuthError(
            `Session invalidated: ${data.reason}`,
            ErrorSeverity.HIGH,
            'WebSocketSessionInvalid'
        );
        this.setDesiredState({ connected: false }); // Trigger disconnect via desired state change
        this.emit('auth_failed', { reason: `Session invalidated: ${data.reason}` });
     });


    // --- ConnectionResilienceManager Listeners ---
    this.resilienceManager.subscribe('reconnect_scheduled', (data: any) => {
        if (this.isDisposed) return;
        this.logger.info(`Resilience: Reconnection scheduled: attempt ${data.attempt}/${data.maxAttempts} in ${data.delay}ms`);
        // Ensure state reflects recovery attempt is active
        appState.updateConnectionState({ isRecovering: true, recoveryAttempt: data.attempt });
    });
    this.resilienceManager.subscribe('reconnect_success', () => {
         if (this.isDisposed) return;
         this.logger.info('Resilience: Connection recovery successful');
         // State (isRecovering: false) is updated when WS reports CONNECTED status
    });
    this.resilienceManager.subscribe('reconnect_failure', (data: any) => {
         if (this.isDisposed) return;
         this.logger.warn(`Resilience: Reconnection attempt ${data.attempt} failed`);
         // State remains isRecovering=true until max attempts or success
         // Update last error message in state maybe?
         appState.updateConnectionState({
            lastConnectionError: `Reconnection attempt ${data.attempt} failed.`
         });
    });
     this.resilienceManager.subscribe('max_attempts_reached', (data: any) => {
         if (this.isDisposed) return;
         const errorMsg = `Failed to reconnect after ${data.maxAttempts} attempts. Please check your connection or try again later.`;
         this.logger.error(`Resilience: ${errorMsg}`);
         appState.updateConnectionState({
             isRecovering: false,
             lastConnectionError: `Failed to reconnect after ${data.maxAttempts} attempts.`,
             webSocketStatus: ConnectionStatus.DISCONNECTED // Ensure status is disconnected
         });
         AppErrorHandler.handleConnectionError(
            errorMsg, // User-friendly message
            ErrorSeverity.HIGH,
            'ConnectionResilienceMaxAttempts'
         );
    });
    this.resilienceManager.subscribe('suspended', (data: any) => {
        if (this.isDisposed) return;
        // FIX: Use suspensionTimeoutMs from options
        const suspensionDuration = this.resilienceManager.options.suspensionTimeoutMs / 1000;
        const errorMsg = `Connection attempts suspended for ${suspensionDuration}s due to ${data.failureCount} failures.`;
        this.logger.error(`Resilience: ${errorMsg}`);
         appState.updateConnectionState({
            isRecovering: false,
            lastConnectionError: `Connection attempts suspended due to repeated failures.`,
             webSocketStatus: ConnectionStatus.DISCONNECTED // Ensure status is disconnected
         });
          // Optional: Notify user via AppErrorHandler?
          AppErrorHandler.handleConnectionError(errorMsg, ErrorSeverity.MEDIUM, 'ConnectionSuspended');
    });
    this.resilienceManager.subscribe('resumed', () => {
         if (this.isDisposed) return;
         this.logger.info(`Resilience: Connection attempts can resume.`);
         appState.updateConnectionState({ lastConnectionError: null }); // Clear suspension error message
         // If desired state is still connected, try connecting again
         this.syncConnectionState();
    });


    // --- Auth State Listener ---
    this.subscriptions.add(
        appState.getAuthState$().subscribe(authState => {
            if (this.isDisposed) return;
             this.logger.debug(`Auth state changed: isAuthenticated=${authState.isAuthenticated}`);
            this.resilienceManager.updateAuthState(authState.isAuthenticated);

            if (!authState.isAuthenticated && !authState.isAuthLoading) {
                const currentState = appState.getState().connection;
                if (currentState.webSocketStatus !== ConnectionStatus.DISCONNECTED || currentState.isRecovering) {
                    this.logger.info('Authentication lost, forcing disconnect.');
                    this.setDesiredState({ connected: false });
                }
            }
        })
    );

    this.logger.info('ConnectionManager event listeners setup complete');
  }

  /**
   * Sets the desired state and triggers synchronization.
   */
  public setDesiredState(state: Partial<ConnectionDesiredState>): void {
    if (this.isDisposed) {
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

  /**
   * Tries to match the actual connection state to the desired state.
   */
  private syncConnectionState(): void {
    if (this.isDisposed || this.resilienceManager.getState().state === 'suspended') {
        this.logger.debug(`Sync connection state skipped: Disposed or Suspended (State: ${this.resilienceManager.getState().state})`);
        return;
    }

    const currentConnState = appState.getState().connection;
    const isConnected = currentConnState.webSocketStatus === ConnectionStatus.CONNECTED;
    const isConnecting = currentConnState.webSocketStatus === ConnectionStatus.CONNECTING;
    const isRecovering = currentConnState.isRecovering; // Check appState's isRecovering flag

    if (this.desiredState.connected && !isConnected && !isConnecting && !isRecovering) {
      this.logger.info('Syncing connection state: attempting to connect');
      this.connect().catch(err => {
        this.logger.error('Connection attempt failed during state sync', { error: err instanceof Error ? err.message : String(err) });
      });
    } else if (!this.desiredState.connected && (isConnected || isConnecting || isRecovering)) {
      this.logger.info('Syncing connection state: disconnecting');
      this.disconnect('desired_state_change');
    } else {
         this.logger.debug('Sync connection state: No action needed.', { desired: this.desiredState.connected, isConnected, isConnecting, isRecovering });
    }
  }

   /**
   * Tries to match the actual simulator state to the desired state.
   */
  private async syncSimulatorState(): Promise<void> {
    if (this.isDisposed) return;

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


  /**
   * Core connection logic: validate session, connect WebSocket.
   * Updates AppState directly.
   */
  public async connect(): Promise<boolean> {
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
      if (this.isDisposed) return false;

      if (!this.tokenManager.isAuthenticated()) {
        this.logger.error('Cannot connect: Not authenticated');
        appState.updateConnectionState({ webSocketStatus: ConnectionStatus.DISCONNECTED, lastConnectionError: 'Authentication required' });
        appState.updateAuthState({ isAuthenticated: false, isAuthLoading: false });
        return false;
      }

      this.logger.info('Attempting to establish connection...');
      // Update state FIRST to prevent rapid re-calls
      appState.updateConnectionState({
          webSocketStatus: ConnectionStatus.CONNECTING,
          lastConnectionError: null,
          isRecovering: false // Mark as not recovering during initial attempt
      });

      try {
        this.logger.info('Validating session with backend...');
        const sessionResponse = await this.sessionApi.createSession();
        if (this.isDisposed) return false;

        if (!sessionResponse.success) {
          throw new Error(`Session Error: ${sessionResponse.errorMessage || 'Failed to establish session'}`);
        }
        this.logger.info('Session validated successfully.');

        this.logger.info('Connecting WebSocket...');
        // wsManager updates AppState internally on success/failure
        const wsConnected = await this.wsManager.connect();
        if (this.isDisposed) {
             if (wsConnected) this.wsManager.disconnect('disposed_during_connect'); // FIX: Use disconnect method
            return false;
        }

        if (!wsConnected) {
           // wsManager should have set state to DISCONNECTED + error
           this.logger.error('WebSocket connection failed after session validation.');
           this.resilienceManager.recordFailure('WebSocket failed to connect');
           this.attemptRecovery('ws_connect_failed'); // Start recovery attempts
           return false;
        }

        this.logger.info('Connection established successfully.');
        this.resilienceManager.reset(); // Reset failures on successful connect
        // wsManager should have set state to CONNECTED
        this.syncSimulatorState();
        return true;

      } catch (error: any) {
        if (this.isDisposed) return false;
        const errorMessage = error instanceof Error ? error.message : String(error);
        this.logger.error('Connection process failed', { error: errorMessage });

        appState.updateConnectionState({
          webSocketStatus: ConnectionStatus.DISCONNECTED,
          isRecovering: false, // Failed initial connect, not yet recovering
          lastConnectionError: errorMessage
        });

        this.resilienceManager.recordFailure(errorMessage);
        this.attemptRecovery('initial_connect_failed');

        AppErrorHandler.handleConnectionError(errorMessage, ErrorSeverity.HIGH, 'ConnectionManager.connect');
        return false;
      }
    });
  }

  /**
   * Disconnects the WebSocket, updates state.
   */
  public disconnect(reason: string = 'manual_disconnect'): void {
    if (this.isDisposed && reason !== 'manager_disposed') {
      this.logger.info(`Disconnect called on disposed ConnectionManager. Reason: ${reason}`);
      return;
    }
    const currentState = appState.getState().connection;
    const wasConnectedOrConnecting = currentState.webSocketStatus !== ConnectionStatus.DISCONNECTED || currentState.isRecovering;

    if (!wasConnectedOrConnecting) {
        this.logger.debug(`Disconnect call ignored: Already disconnected. Reason: ${reason}`);
        return; // Avoid redundant disconnects/logs
    }

    this.logger.warn(`Disconnecting. Reason: ${reason}`);

    this.resilienceManager.reset(); // Stop any recovery attempts

    // FIX: Use disconnect method
    this.wsManager.disconnect(reason); // wsManager updates state internally

    // Ensure AppState reflects final disconnected state
     appState.updateConnectionState({
         webSocketStatus: ConnectionStatus.DISCONNECTED,
         isRecovering: false,
         quality: ConnectionQuality.UNKNOWN,
         heartbeatLatency: null,
         lastHeartbeatTime: undefined,
         lastConnectionError: `Disconnected: ${reason}`,
         // Update simulator status if it was running
         ...(currentState.simulatorStatus === 'RUNNING' && { simulatorStatus: 'UNKNOWN' })
     });
  }

  /**
   * Initiates the connection recovery process via the resilience manager.
   */
  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    if (this.isDisposed) return false;

    const resilienceState = this.resilienceManager.getState();
    if (appState.getState().connection.isRecovering || resilienceState.state === 'suspended') {
       this.logger.warn(`Recovery attempt ignored: Already recovering or suspended. Reason: ${reason}`);
       return false;
    }

    this.logger.warn(`Connection recovery requested. Reason: ${reason}`);
    // Update state to show recovery is starting
    appState.updateConnectionState({ isRecovering: true, recoveryAttempt: 1 });

    this.resilienceManager.attemptReconnection(() => this.connect())
        .then(initiated => {
            if (!initiated && !this.isDisposed) {
                // Recovery couldn't start (e.g., max attempts, suspended, auth error)
                // Ensure state doesn't incorrectly show 'recovering'
                this.logger.warn("Recovery process could not be initiated.");
                 if(appState.getState().connection.isRecovering) {
                    appState.updateConnectionState({ isRecovering: false, recoveryAttempt: 0 });
                 }
            }
        });

    return true;
  }

   // --- Direct Actions (Proxied to underlying managers) ---

  public async submitOrder(order: {
    symbol: string;
    side: OrderSide;
    quantity: number;
    price?: number;
    type: OrderType;
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
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
    this.logger.info('Submitting order', { symbol: order.symbol, type: order.type, side: order.side });
    return this.dataHandlers.submitOrder(order);
  }

  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
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

  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
     this.desiredState.simulatorRunning = true; // Set intent
     const state = appState.getState().connection;
     if (state.webSocketStatus !== ConnectionStatus.CONNECTED) {
       const errorMsg = 'Start simulator failed: Not connected';
       return { success: false, error: errorMsg };
     }
     if (state.simulatorStatus === 'RUNNING' || state.simulatorStatus === 'STARTING') {
        this.logger.warn(`Start simulator ignored: Already ${state.simulatorStatus}`);
        return { success: true, status: state.simulatorStatus };
     }

     this.logger.info('Starting simulator...');
     appState.updateConnectionState({ simulatorStatus: 'STARTING' });
     try {
         const result = await this.simulatorManager.startSimulator();
         if (this.isDisposed) return { success: false, error: 'Disposed during start' };
         appState.updateConnectionState({
             simulatorStatus: result.success ? (result.status || 'RUNNING') : 'ERROR',
             lastConnectionError: result.success ? null : (result.errorMessage || 'Failed to start simulator')
         });
         if (!result.success) {
             this.desiredState.simulatorRunning = false;
             AppErrorHandler.handleGenericError(result.errorMessage || 'Failed to start simulator', ErrorSeverity.MEDIUM, 'StartSimulator');
         }
         // Return API response format
         return { success: result.success, status: result.status, error: result.errorMessage };
     } catch (error: any) {
         if (this.isDisposed) return { success: false, error: 'Disposed during start exception' };
          const errorMsg = error instanceof Error ? error.message : String(error);
          this.logger.error('Error starting simulator', { error: errorMsg });
          appState.updateConnectionState({ simulatorStatus: 'ERROR', lastConnectionError: errorMsg });
          this.desiredState.simulatorRunning = false;
          AppErrorHandler.handleGenericError(errorMsg, ErrorSeverity.HIGH, 'StartSimulatorException');
          return { success: false, error: errorMsg };
     }
  }

  public async stopSimulator(): Promise<{ success: boolean; status?: string; error?: string }> { // Match return type of start
     if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
      this.desiredState.simulatorRunning = false; // Set intent
      const state = appState.getState().connection;
      if (state.webSocketStatus !== ConnectionStatus.CONNECTED) {
        const errorMsg = 'Stop simulator failed: Not connected';
        return { success: false, error: errorMsg };
      }
       if (state.simulatorStatus !== 'RUNNING' && state.simulatorStatus !== 'STARTING') { // Allow stopping if starting
           this.logger.warn(`Stop simulator ignored: Not running or starting (status: ${state.simulatorStatus})`);
           return { success: true, status: state.simulatorStatus };
       }

      this.logger.info('Stopping simulator...');
      appState.updateConnectionState({ simulatorStatus: 'STOPPING' });
      try {
          const result = await this.simulatorManager.stopSimulator();
          if (this.isDisposed) return { success: false, error: 'Disposed during stop' };
          const simStatus = result.success ? 'STOPPED' : 'ERROR';
          const errorMsg = result.success ? null : (result.errorMessage || 'Failed to stop simulator');
          appState.updateConnectionState({ simulatorStatus: simStatus, lastConnectionError: errorMsg });
          if (!result.success) {
              // Don't revert desired state for stop failure
               AppErrorHandler.handleGenericError(errorMsg || 'Failed to stop simulator', ErrorSeverity.MEDIUM, 'StopSimulator');
          }
          // Return API response format
          return { success: result.success, status: result.status, error: result.errorMessage };
      } catch (error: any) {
          if (this.isDisposed) return { success: false, error: 'Disposed during stop exception' };
           const errorMsg = error instanceof Error ? error.message : String(error);
           this.logger.error('Error stopping simulator', { error: errorMsg });
           appState.updateConnectionState({ simulatorStatus: 'ERROR', lastConnectionError: errorMsg });
           AppErrorHandler.handleGenericError(errorMsg, ErrorSeverity.HIGH, 'StopSimulatorException');
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


  /**
   * Disposes of resources.
   */
  public dispose(): void {
    if (this.isDisposed) return;
    this.logger.warn('Disposing ConnectionManager');
    this.isDisposed = true;
    this.disconnect('manager_disposed'); // Also resets resilience
    if (this.resilienceManager && typeof this.resilienceManager.dispose === 'function') {
        this.resilienceManager.dispose();
    }
    if (this.wsManager && typeof this.wsManager.dispose === 'function') {
        this.wsManager.dispose();
    }
    this.subscriptions.unsubscribe();
    this.removeAllListeners();
    this.logger.info('ConnectionManager disposed');
  }

  [Symbol.dispose](): void {
    this.dispose();
  }
}