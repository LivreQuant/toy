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
import { OrderSide, OrderType, SubmitOrderRequest, SubmitOrderResponse } from '../../api/order';
import { SimulatorStatusResponse } from '../../api/simulator';
import { EnhancedLogger } from '../../utils/enhanced-logger';
import { getLogger } from '../../boot/logging';
import { TypedEventEmitter } from '../../utils/typed-event-emitter';

// *** TEMPORARY TOP-LEVEL LOG ***
console.log('>>> ConnectionManager module loaded <<<'); // For verifying file load
const moduleLogger = getLogger('ConnectionManager'); // Get instance for constructor

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

// Type aliases for return values
type SubmitOrderResult = { success: boolean; orderId?: string; error?: string };
type CancelOrderResult = { success: boolean; error?: string };
type SimulatorActionResult = { success: boolean; status?: string; error?: string };


export class ConnectionManager extends TypedEventEmitter<ConnectionManagerEvents> implements Disposable {
  // Use protected logger inherited from TypedEventEmitter
  protected logger: EnhancedLogger;
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
    const loggerInstance = moduleLogger; // Use instance from module scope
    // Call super() ONCE before using 'this'
    super(loggerInstance);
    // Assign logger to the instance property
    this.logger = loggerInstance;
    // *** TEMPORARY CONSTRUCTOR LOG ***
    console.log('>>> ConnectionManager CONSTRUCTOR running (super called) <<<');

    this.logger.info('ConnectionManager initializing...', { options });

    // --- Service Instantiation ---
    this.tokenManager = tokenManager;
    this.httpClient = new HttpClient(tokenManager);
    this.sessionApi = new SessionApi(this.httpClient);
    this.dataHandlers = new ConnectionDataHandlers(this.httpClient);
    this.simulatorManager = new ConnectionSimulatorManager(this.httpClient);
    this.wsManager = new WebSocketManager(
      tokenManager,
      { ...options.wsOptions, preventAutoConnect: true }
    );
    // Resilience Manager Setup
    const resilienceOptions = options.resilience ? {
        initialDelayMs: options.resilience.initialDelayMs, maxDelayMs: options.resilience.maxDelayMs,
        maxAttempts: options.resilience.maxAttempts, suspensionTimeoutMs: options.resilience.suspensionTimeoutMs,
        failureThreshold: options.resilience.failureThreshold, jitterFactor: options.resilience.jitterFactor
    } : undefined;
    this.resilienceManager = new ConnectionResilienceManager(
      tokenManager,
      this.logger, // Pass this logger instance as parent
      resilienceOptions
    );

    this.setupEventListeners();
    this.logger.info('ConnectionManager initialized');
  }

  // --- Private Methods ---

  private setupEventListeners(): void {
    this.logger.debug('Setting up ConnectionManager event listeners');

    // --- WebSocketManager Listeners ---
    this.subscriptions.add(
        this.wsManager.getConnectionStatus().subscribe(status => {
            if (this.isDisposed) return;
             this.logger.debug(`[Listener] WebSocketManager status changed: ${status}`);
            // Handle different statuses
            if (status === ConnectionStatus.DISCONNECTED && this.desiredState.connected) {
               this.logger.warn('[Listener] WebSocket disconnected unexpectedly. Attempting recovery.');
               this.attemptRecovery('ws_unexpected_disconnect');
            } else if (status === ConnectionStatus.CONNECTED) {
                this.logger.info('[Listener] WebSocket connected. Resetting resilience.');
                this.resilienceManager.reset(); // Reset on successful connection
                 // Ensure global state matches if not already set
                 if (appState.getState().connection.webSocketStatus !== ConnectionStatus.CONNECTED) {
                     appState.updateConnectionState({ webSocketStatus: ConnectionStatus.CONNECTED, isRecovering: false, recoveryAttempt: 0, lastConnectionError: null });
                 }
                this.syncSimulatorState(); // Attempt to sync simulator state now that we are connected
            } else if (status === ConnectionStatus.DISCONNECTED) {
                // Ensure global state matches if WS reports disconnect
                 if (appState.getState().connection.webSocketStatus !== ConnectionStatus.DISCONNECTED) {
                     this.logger.warn('[Listener] WebSocket transitioned to DISCONNECTED. Updating app state.');
                     appState.updateConnectionState({ webSocketStatus: ConnectionStatus.DISCONNECTED, isRecovering: false });
                 }
            }
        })
    );
     // Session Invalidated by Server
     this.wsManager.subscribe('session_invalidated', (data) => {
        if (this.isDisposed) return;
        this.logger.error(`[Listener] Session invalidated by server. Reason: ${data.reason}. Forcing disconnect and logout.`);
        AppErrorHandler.handleAuthError(`Session invalidated: ${data.reason}`, ErrorSeverity.HIGH, 'WebSocketSessionInvalid');
        this.setDesiredState({ connected: false }); // Trigger disconnect flow
        this.emit('auth_failed', { reason: `Session invalidated: ${data.reason}` }); // Notify listeners
     });

    // --- ConnectionResilienceManager Listeners ---
    this.resilienceManager.subscribe('reconnect_scheduled', (data: any) => {
        if (this.isDisposed) return;
        this.logger.info(`[Listener][Resilience] Reconnection scheduled: attempt ${data.attempt}/${data.maxAttempts} in ${data.delay}ms`);
        appState.updateConnectionState({ isRecovering: true, recoveryAttempt: data.attempt });
    });
     this.resilienceManager.subscribe('reconnect_success', () => {
         if (this.isDisposed) return;
         this.logger.info('[Listener][Resilience] Connection recovery successful');
         // Note: State transition to CONNECTED is handled by the wsManager listener above
    });
    this.resilienceManager.subscribe('reconnect_failure', (data: any) => {
         if (this.isDisposed) return;
         this.logger.warn(`[Listener][Resilience] Reconnection attempt ${data.attempt} failed`);
         // Update error, state remains isRecovering=true until max attempts or success
         appState.updateConnectionState({ lastConnectionError: `Reconnection attempt ${data.attempt} failed.` });
    });
     this.resilienceManager.subscribe('max_attempts_reached', (data: any) => {
         if (this.isDisposed) return;
         const errorMsg = `Failed to reconnect after ${data.maxAttempts} attempts. Check connection or try later.`;
         this.logger.error(`[Listener][Resilience] ${errorMsg}`);
         appState.updateConnectionState({ isRecovering: false, lastConnectionError: `Failed after ${data.maxAttempts} attempts.`, webSocketStatus: ConnectionStatus.DISCONNECTED });
         AppErrorHandler.handleConnectionError( errorMsg, ErrorSeverity.HIGH, 'ConnectionResilienceMaxAttempts' );
    });
    this.resilienceManager.subscribe('suspended', (data: any) => {
         if (this.isDisposed) return;
         const suspensionDuration = this.resilienceManager.options.suspensionTimeoutMs / 1000;
         const errorMsg = `Connection attempts suspended for ${suspensionDuration}s after ${data.failureCount} failures.`;
         this.logger.error(`[Listener][Resilience] ${errorMsg}`);
         appState.updateConnectionState({ isRecovering: false, lastConnectionError: `Connection suspended.`, webSocketStatus: ConnectionStatus.DISCONNECTED });
          AppErrorHandler.handleConnectionError(errorMsg, ErrorSeverity.MEDIUM, 'ConnectionSuspended');
    });
    this.resilienceManager.subscribe('resumed', () => {
         if (this.isDisposed) return;
         this.logger.info(`[Listener][Resilience] Connection attempts can resume.`);
         appState.updateConnectionState({ lastConnectionError: null }); // Clear suspension message
         this.syncConnectionState(); // Try to connect again if desired
    });

    // --- Auth State Listener ---
    this.subscriptions.add(
        appState.select(state => state.auth).subscribe(authState => {
            if (this.isDisposed) return;
            this.logger.debug(`[Listener] Auth state changed: isAuthenticated=${authState.isAuthenticated}, isAuthLoading=${authState.isAuthLoading}`);
            this.resilienceManager.updateAuthState(authState.isAuthenticated); // Inform resilience manager

            // Only react *after* initial loading is complete
            if (!authState.isAuthLoading) {
                if (authState.isAuthenticated) {
                    // User is authenticated, trigger connection sync
                    this.logger.info('[Listener] Auth confirmed. Triggering connection state sync.');
                    this.syncConnectionState();
                } else {
                    // User is not authenticated, ensure disconnected
                    const currentState = appState.getState().connection;
                    if (currentState.webSocketStatus !== ConnectionStatus.DISCONNECTED || currentState.isRecovering) {
                        this.logger.info('[Listener] Authentication lost or absent, ensuring disconnect.');
                        this.setDesiredState({ connected: false }); // This triggers sync -> disconnect
                    } else {
                         this.logger.debug('[Listener] Not authenticated and already disconnected.');
                    }
                }
            }
        })
    );
    this.logger.debug('ConnectionManager event listeners setup complete');
  }

  public setDesiredState(state: Partial<ConnectionDesiredState>): void {
    // *** TEMPORARY LOG ***
    console.log(`*** ConnectionManager: setDesiredState called with: ${JSON.stringify(state)} ***`);
    if (this.isDisposed) {
      this.logger.error('Cannot set desired state: ConnectionManager is disposed');
      return;
    }
    this.logger.info(`Setting desired state: ${JSON.stringify(state)}`);

    // Check if state actually changed
    const changed = Object.keys(state).some(
        key => this.desiredState[key as keyof ConnectionDesiredState] !== state[key as keyof ConnectionDesiredState]
    );
    if (!changed) {
        this.logger.debug('Desired state unchanged, skipping sync.');
        return;
    }

    // Update state and trigger sync
    const oldState = { ...this.desiredState };
    this.desiredState = { ...this.desiredState, ...state };
    this.logger.info('Desired state updated', { oldState, newState: this.desiredState });
    this.logger.debug('Triggering state sync after desired state change.');
    this.syncConnectionState();
    this.syncSimulatorState(); // Sync simulator state as well
  }

  private syncConnectionState(): void {
    // *** TEMPORARY LOG ***
    console.log('*** ConnectionManager: syncConnectionState CALLED ***');
    this.logger.debug('syncConnectionState called.');

    // --- GUARD 1: Check if disposed ---
    if (this.isDisposed) {
        console.log('*** syncConnectionState EXITING due to guard: DISPOSED ***');
        this.logger.debug('syncConnectionState skipped: Disposed.');
        return;
    }

    const currentAuthState = appState.getState().auth;
    const resilienceInfo = this.resilienceManager.getState();

    // *** Log states (changed to WARN for visibility) ***
    this.logger.warn(`syncConnectionState - States Check: AuthLoading=${currentAuthState.isAuthLoading}, Authenticated=${currentAuthState.isAuthenticated}, Resilience=${resilienceInfo.state}`);

    // --- GUARD 2: Check if auth is still loading ---
    if (currentAuthState.isAuthLoading) {
        console.log('*** syncConnectionState EXITING due to guard: AUTH LOADING ***');
        this.logger.debug('syncConnectionState skipped: Authentication is loading.');
        return;
    }
    // --- GUARD 3: Check if resilience manager is preventing connections ---
    if (resilienceInfo.state === 'suspended' || resilienceInfo.state === 'failed') {
        console.log(`*** syncConnectionState EXITING due to guard: RESILIENCE STATE (${resilienceInfo.state}) ***`);
        this.logger.warn(`syncConnectionState skipped: Resilience state is ${resilienceInfo.state}.`);
        return;
    }

    // --- Past Initial Guards ---
    console.log('*** syncConnectionState: Passed initial guards ***'); // Confirm guards passed

    const currentConnState = appState.getState().connection;
    const isConnected = currentConnState.webSocketStatus === ConnectionStatus.CONNECTED;
    const isConnecting = currentConnState.webSocketStatus === ConnectionStatus.CONNECTING;
    const isRecovering = currentConnState.isRecovering;

    this.logger.debug(`syncConnectionState - Connection Vars: Desired=${this.desiredState.connected}, isConnected=${isConnected}, isConnecting=${isConnecting}, isRecovering=${isRecovering}`);
    // Log check variables
    console.log(`*** syncConnectionState Check Values: desired.connected=${this.desiredState.connected}, !isConnected=${!isConnected}, !isConnecting=${!isConnecting}, !isRecovering=${!isRecovering} ***`);

    // --- GUARD 4: Check if trying to connect but not authenticated ---
    if (this.desiredState.connected && !currentAuthState.isAuthenticated) {
        console.log('*** syncConnectionState EXITING due to guard: NOT AUTHENTICATED (Guard 4) ***');
        this.logger.warn('syncConnectionState decision: Cannot connect, user not authenticated.');
        if (isConnected || isConnecting || isRecovering) {
           this.disconnect('not_authenticated_sync');
        }
        return;
    }

    // --- The Decision Point ---
    if (this.desiredState.connected && !isConnected && !isConnecting && !isRecovering) { // CONDITION TO CONNECT
      this.logger.info('syncConnectionState decision: Attempting connect.');
      console.log('*** ConnectionManager: syncConnectionState - DECISION: Connect ***');
      this.connect().catch(err => { this.logger.error('syncConnectionState: Connect call returned an error', { error: err instanceof Error ? err.message : String(err) }); });
    }
    else if (!this.desiredState.connected && (isConnected || isConnecting || isRecovering)) { // CONDITION TO DISCONNECT
      this.logger.info('syncConnectionState decision: Attempting disconnect.');
      console.log('*** ConnectionManager: syncConnectionState - DECISION: Disconnect ***');
      this.disconnect('desired_state_false_sync');
    }
    else { // CONDITION FOR NO ACTION
      this.logger.debug('syncConnectionState decision: No action needed.');
      console.log('*** ConnectionManager: syncConnectionState - DECISION: No Action ***');
    }
  }

  private async syncSimulatorState(): Promise<void> {
     if (this.isDisposed) return;
     const currentConnState = appState.getState().connection;
     const isConnected = currentConnState.webSocketStatus === ConnectionStatus.CONNECTED;
     if (!isConnected) { this.logger.debug('Sync sim state skipped: Not connected.'); return; }
     const currentSimStatus = currentConnState.simulatorStatus;
     const isRunning = currentSimStatus === 'RUNNING';
     const isBusy = currentSimStatus === 'STARTING' || currentSimStatus === 'STOPPING';
     // Sync logic based on desired state and current status
     if (this.desiredState.simulatorRunning && !isRunning && !isBusy) { this.logger.info('Sync sim state: starting...'); await this.startSimulator(); }
     else if (!this.desiredState.simulatorRunning && isRunning && !isBusy) { this.logger.info('Sync sim state: stopping...'); await this.stopSimulator(); }
     else { this.logger.debug('Sync sim state: No action needed.', { desired: this.desiredState.simulatorRunning, currentStatus: currentSimStatus }); }
   }

  public async connect(): Promise<boolean> {
    // *** TEMPORARY LOG ***
    console.log('*** ConnectionManager: connect CALLED ***');
    this.logger.info('connect() method invoked.');

     // --- Guards ---
     if (this.isDisposed) { this.logger.warn('connect() aborted: Disposed.'); return false; }
     const currentAuthState = appState.getState().auth;
     if (currentAuthState.isAuthLoading) { this.logger.warn('connect() aborted: Auth loading.'); return false; }
     if (!currentAuthState.isAuthenticated) { this.logger.error('connect() aborted: Not authenticated.'); appState.updateConnectionState({ webSocketStatus: ConnectionStatus.DISCONNECTED, lastConnectionError: 'Auth required', isRecovering: false }); return false; }
     const currentConnState = appState.getState().connection;
     const resilienceInfo = this.resilienceManager.getState();
     if (currentConnState.webSocketStatus === ConnectionStatus.CONNECTING || currentConnState.webSocketStatus === ConnectionStatus.CONNECTED) { this.logger.warn(`connect() ignored: Status=${currentConnState.webSocketStatus}`); return currentConnState.webSocketStatus === ConnectionStatus.CONNECTED; }
     if (currentConnState.isRecovering || resilienceInfo.state === 'suspended' || resilienceInfo.state === 'failed') { this.logger.warn(`connect() ignored: Recovering or Resilience=${resilienceInfo.state}.`); return false; }
     // --- End Guards ---

    // Wrap actual connection logic in timed block
    return this.logger.trackTime('connect_process', async () => {
      if (this.isDisposed) return false; // Re-check inside async
      if (!this.tokenManager.isAuthenticated()) { this.logger.error('connect() aborted: Not authenticated (re-check)'); appState.updateConnectionState({ webSocketStatus: ConnectionStatus.DISCONNECTED, lastConnectionError: 'Auth required' }); return false; }

      this.logger.info('connect(): Attempting connection process...');
      // Set state to CONNECTING
      appState.updateConnectionState({ webSocketStatus: ConnectionStatus.CONNECTING, lastConnectionError: null, isRecovering: false });

      let sessionOk = false;
      let wsOk = false;
      try {
        // 1. Validate Session (HTTP)
        this.logger.debug('connect(): Validating session via API...');
        console.log('*** CM: connect - BEFORE sessionApi.createSession() ***');
        const sessionResponse = await this.sessionApi.createSession();
        console.log(`*** CM: connect - AFTER sessionApi.createSession(), success: ${sessionResponse?.success} ***`);
        if (this.isDisposed) return false; // Check again after await
        if (!sessionResponse.success) {
          this.logger.error('connect(): Session validation failed.', { error: sessionResponse.errorMessage });
          throw new Error(`Session Error: ${sessionResponse.errorMessage || 'Failed session validation'}`);
        }
        this.logger.info('connect(): Session validated successfully.');
        sessionOk = true;

        // 2. Connect WebSocket
        this.logger.debug('connect(): Connecting WebSocket via wsManager...');
        console.log('*** CM: connect - BEFORE wsManager.connect() ***');
        wsOk = await this.wsManager.connect(); // wsManager handles actual WebSocket creation/events
        console.log(`*** CM: connect - AFTER wsManager.connect(), result: ${wsOk} ***`);
        if (this.isDisposed) { if (wsOk) this.wsManager.disconnect('disposed_during_connect'); return false; } // Check again

        // Check WebSocket connection result
        if (!wsOk) {
           this.logger.error('connect(): wsManager.connect() returned false (connection failed).');
           // Ensure state reflects failure if not already set by listener
           if (!appState.getState().connection.lastConnectionError) { appState.updateConnectionState({ lastConnectionError: 'WebSocket connection failed', webSocketStatus: ConnectionStatus.DISCONNECTED }); }
           // Trigger recovery process
           this.resilienceManager.recordFailure('WebSocket failed post-session');
           this.attemptRecovery('ws_connect_failed_post_session');
           return false; // Indicate connection failure
        }

        // If wsOk is true, the wsManager listener should handle setting state to CONNECTED
        this.logger.info('connect(): Connection process initiated successfully (WebSocket connecting/connected).');
        return true; // Indicate success (or at least successful initiation)

      } catch (error: any) {
        // Catch errors from session validation or potentially wsManager.connect if it throws
        console.error(`*** CM: connect - ERROR caught in process: ${error?.message} ***`, error);
        if (this.isDisposed) return false;
        const errorMessage = error instanceof Error ? error.message : String(error);
        this.logger.error(`connect(): Connection process failed during ${sessionOk ? 'WebSocket connection phase' : 'session validation phase'}.`, { error: errorMessage });
        // Set state to disconnected on error
        appState.updateConnectionState({ webSocketStatus: ConnectionStatus.DISCONNECTED, isRecovering: false, lastConnectionError: errorMessage });
        // Trigger recovery process
        this.resilienceManager.recordFailure(`Connection process error: ${errorMessage}`);
        this.attemptRecovery('connect_process_exception');
        // Handle global error notification
        AppErrorHandler.handleConnectionError(errorMessage, ErrorSeverity.HIGH, 'ConnectionManager.connect');
        return false; // Indicate connection failure
      }
    });
  }

  public disconnect(reason: string = 'manual_disconnect'): void {
    this.logger.info(`disconnect() called. Reason: ${reason}`);
    if (this.isDisposed && reason !== 'manager_disposed') { this.logger.debug(`Disconnect ignored: Disposed.`); return; }
     const currentState = appState.getState().connection;
     const wasConnectedOrConnecting = currentState.webSocketStatus !== ConnectionStatus.DISCONNECTED || currentState.isRecovering;
     if (!wasConnectedOrConnecting) { this.logger.debug(`Disconnect ignored: Already disconnected.`); return; }

     this.logger.warn(`Disconnecting internal state. Reason: ${reason}`);
     this.resilienceManager.reset(); // Reset resilience state on disconnect
     this.wsManager.disconnect(reason); // Tell WebSocketManager to close the socket

     // Immediately update app state to reflect disconnection
     appState.updateConnectionState({
         webSocketStatus: ConnectionStatus.DISCONNECTED,
         isRecovering: false,
         quality: ConnectionQuality.UNKNOWN,
         heartbeatLatency: null,
         lastHeartbeatTime: undefined,
         lastConnectionError: `Disconnected: ${reason}`,
         // Reset simulator status if it wasn't already stopped/unknown
         ...(currentState.simulatorStatus !== 'STOPPED' && currentState.simulatorStatus !== 'UNKNOWN' && { simulatorStatus: 'UNKNOWN' })
     });
  }

   public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
     this.logger.info(`attemptRecovery() called. Reason: ${reason}`);
     if (this.isDisposed) { this.logger.debug('Recovery aborted: Disposed.'); return false; }

     // --- Guards ---
     const currentAuthState = appState.getState().auth;
     if (currentAuthState.isAuthLoading) { this.logger.warn(`Recovery ignored: Auth loading.`); return false; }
     if (!currentAuthState.isAuthenticated) { this.logger.warn(`Recovery ignored: Not authenticated.`); return false; }
     const resilienceInfo = this.resilienceManager.getState();
     const currentConnState = appState.getState().connection;
     if (currentConnState.isRecovering || resilienceInfo.state === 'suspended' || resilienceInfo.state === 'failed') { this.logger.warn(`Recovery ignored: Already recovering or Resilience=${resilienceInfo.state}.`); return false; }
     // --- End Guards ---

     this.logger.warn(`Connection recovery requested via resilience manager. Reason: ${reason}`);
     // Optimistically update state to show recovery starting
     appState.updateConnectionState({ isRecovering: true, recoveryAttempt: resilienceInfo.attempt + 1 });

     // Delegate to resilience manager
     const initiated = await this.resilienceManager.attemptReconnection(() => this.connect());

     // Handle case where resilience manager couldn't initiate (e.g., max attempts already reached)
     if (!initiated && !this.isDisposed) {
          this.logger.warn("Recovery could not be initiated by resilience manager.");
           // Revert optimistic state if recovery didn't actually start
           if(appState.getState().connection.isRecovering) {
              appState.updateConnectionState({ isRecovering: false, recoveryAttempt: 0 });
           }
      } else if (initiated) {
          this.logger.info("Recovery initiated by resilience manager.");
      }
     return initiated; // Return whether initiation was successful
   }

  // --- Public Actions ---
  // (Implementations unchanged, only signatures were fixed previously)
  public async submitOrder(order: SubmitOrderRequest): Promise<SubmitOrderResult> { if (this.isDisposed) return { success: false, error: 'CM disposed' }; const s=appState.getState().connection; if (s.webSocketStatus!==ConnectionStatus.CONNECTED){const e='Submit fail: Not connected'; AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'SubmitOrderCheck'); return { success: false, error: e };} if (s.simulatorStatus!=='RUNNING'){const e='Submit fail: Sim not running'; AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'SubmitOrderCheck'); return { success: false, error: e };} this.logger.info('Submitting order',{/*...*/}); return this.dataHandlers.submitOrder(order); }
  public async cancelOrder(orderId: string): Promise<CancelOrderResult> { if (this.isDisposed) return { success: false, error: 'CM disposed' }; const s=appState.getState().connection; if (s.webSocketStatus!==ConnectionStatus.CONNECTED){const e='Cancel fail: Not connected'; AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'CancelOrderCheck'); return { success: false, error: e };} if (s.simulatorStatus!=='RUNNING'){const e='Cancel fail: Sim not running'; AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'CancelOrderCheck'); return { success: false, error: e };} this.logger.info('Cancelling order',{orderId}); return this.dataHandlers.cancelOrder(orderId); }
  public async startSimulator(): Promise<SimulatorActionResult> { if (this.isDisposed) return { success: false, error: 'CM disposed' }; this.desiredState.simulatorRunning=true; const s=appState.getState().connection; if (s.webSocketStatus!==ConnectionStatus.CONNECTED){const e='Start sim fail: Not connected'; return { success: false, error: e };} if (s.simulatorStatus==='RUNNING' || s.simulatorStatus==='STARTING'){this.logger.warn(`Start sim ignored: Status=${s.simulatorStatus}`); return { success: true, status: s.simulatorStatus };} this.logger.info('Starting sim...'); appState.updateConnectionState({ simulatorStatus: 'STARTING' }); try { const r: SimulatorStatusResponse = await this.simulatorManager.startSimulator(); if (this.isDisposed) return { success: false, error: 'Disposed' }; appState.updateConnectionState({ simulatorStatus: r.success ? (r.status || 'RUNNING') : 'ERROR', lastConnectionError: r.success ? null : (r.errorMessage || 'Failed start') }); if (!r.success) { this.desiredState.simulatorRunning = false; AppErrorHandler.handleGenericError(r.errorMessage || 'Failed start', ErrorSeverity.MEDIUM, 'StartSim'); } return { success: r.success, status: r.status, error: r.errorMessage }; } catch (error: any) { if (this.isDisposed) return { success: false, error: 'Disposed' }; const e=error instanceof Error ? error.message : String(error); this.logger.error('Error starting sim', { error: e }); appState.updateConnectionState({ simulatorStatus: 'ERROR', lastConnectionError: e }); this.desiredState.simulatorRunning = false; AppErrorHandler.handleGenericError(e, ErrorSeverity.HIGH, 'StartSimEx'); return { success: false, error: e }; } }
  public async stopSimulator(): Promise<SimulatorActionResult> { if (this.isDisposed) return { success: false, error: 'CM disposed' }; this.desiredState.simulatorRunning=false; const s=appState.getState().connection; if (s.webSocketStatus!==ConnectionStatus.CONNECTED){const e='Stop sim fail: Not connected'; return { success: false, error: e };} if (s.simulatorStatus!=='RUNNING' && s.simulatorStatus!=='STARTING'){this.logger.warn(`Stop sim ignored: Status=${s.simulatorStatus}`); return { success: true, status: s.simulatorStatus };} this.logger.info('Stopping sim...'); appState.updateConnectionState({ simulatorStatus: 'STOPPING' }); try { const r: SimulatorStatusResponse = await this.simulatorManager.stopSimulator(); if (this.isDisposed) return { success: false, error: 'Disposed' }; const st=r.success ? 'STOPPED' : 'ERROR'; const e=r.success ? null : (r.errorMessage || 'Failed stop'); appState.updateConnectionState({ simulatorStatus: st, lastConnectionError: e }); if (!r.success) { AppErrorHandler.handleGenericError(e || 'Failed stop', ErrorSeverity.MEDIUM, 'StopSim'); } return { success: r.success, status: r.status, error: result.errorMessage }; } catch (error: any) { if (this.isDisposed) return { success: false, error: 'Disposed' }; const e=error instanceof Error ? error.message : String(error); this.logger.error('Error stopping sim', { error: e }); appState.updateConnectionState({ simulatorStatus: 'ERROR', lastConnectionError: e }); AppErrorHandler.handleGenericError(e, ErrorSeverity.HIGH, 'StopSimEx'); return { success: false, error: e }; } }
  public manualReconnect(): void { this.logger.warn('Manual reconnect via manualReconnect()'); if (this.isDisposed) return; this.setDesiredState({ connected: true }); this.attemptRecovery('manual_user_request'); }


  // --- Dispose ---
  public override dispose(): void {
       if (this.isDisposed) return;
       this.logger.warn('Disposing CM...');
       this.disconnect('manager_disposed');
       if (this.resilienceManager) this.resilienceManager.dispose();
       if (this.wsManager) this.wsManager.dispose();
       this.subscriptions.unsubscribe();
       super.dispose(); // Call base dispose
       this.logger.info('CM disposed.');
   }

  [Symbol.dispose](): void {
    this.dispose();
  }
} // End of ConnectionManager class