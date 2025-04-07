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
import { SimulatorStatusResponse } from '../../api/simulator';
import { EnhancedLogger } from '../../utils/enhanced-logger';
import { getLogger } from '../../boot/logging';
import { TypedEventEmitter } from '../../utils/typed-event-emitter';

// *** TEMPORARY TOP-LEVEL LOG ***
console.log('>>> ConnectionManager module loaded <<<'); // For verifying file load
const moduleLogger = getLogger('ConnectionManager'); // Get instance for constructor

// Define events emitted by this manager
export interface ConnectionManagerEvents {
  auth_failed: { reason: string };
}

// Define the desired state structure
export interface ConnectionDesiredState {
  connected: boolean;
  simulatorRunning: boolean;
}

// Define options for configuring the manager
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

// Define specific return types for public action methods
type SubmitOrderResult = { success: boolean; orderId?: string; error?: string };
type CancelOrderResult = { success: boolean; error?: string };
type SimulatorActionResult = { success: boolean; status?: string; error?: string };


/**
 * Manages the overall application connection lifecycle, including WebSocket,
 * session validation, resilience, and simulator control.
 */
export class ConnectionManager extends TypedEventEmitter<ConnectionManagerEvents> implements Disposable {
  // Inherits logger property and isDisposed getter from TypedEventEmitter
  protected logger: EnhancedLogger;
  private dataHandlers: ConnectionDataHandlers;
  private simulatorManager: ConnectionSimulatorManager;
  private resilienceManager: ConnectionResilienceManager;
  private wsManager: WebSocketManager;
  private tokenManager: TokenManager;
  private sessionApi: SessionApi;
  private httpClient: HttpClient;
  private subscriptions = new Subscription();
  // Holds the desired state requested by the UI or other services
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
    this.httpClient = new HttpClient(tokenManager); // Used by other API clients
    this.sessionApi = new SessionApi(this.httpClient); // For session validation
    this.dataHandlers = new ConnectionDataHandlers(this.httpClient); // For orders etc.
    this.simulatorManager = new ConnectionSimulatorManager(this.httpClient); // For sim control
    // WebSocket Manager setup
    this.wsManager = new WebSocketManager(
      tokenManager,
      { ...options.wsOptions, preventAutoConnect: true } // Ensure CM controls connections
    );
    // Resilience Manager Setup
    const resilienceOptions = options.resilience ? {
        initialDelayMs: options.resilience.initialDelayMs, maxDelayMs: options.resilience.maxDelayMs,
        maxAttempts: options.resilience.maxAttempts, suspensionTimeoutMs: options.resilience.suspensionTimeoutMs,
        failureThreshold: options.resilience.failureThreshold, jitterFactor: options.resilience.jitterFactor
    } : undefined;
    this.resilienceManager = new ConnectionResilienceManager(
      tokenManager,
      this.logger, // Pass this logger instance as parent for hierarchical logging
      resilienceOptions
    );

    // Subscribe to events from dependencies
    this.setupEventListeners();

    this.logger.info('ConnectionManager initialized');
  }

  // --- Private Methods ---

  /**
   * Sets up subscriptions to events from dependencies (Auth state, WS status, Resilience events).
   */
  private setupEventListeners(): void {
    this.logger.debug('Setting up ConnectionManager event listeners');

    // --- WebSocketManager Listeners ---
    this.subscriptions.add(
        this.wsManager.getConnectionStatus().subscribe(status => {
            if (this.isDisposed) return; // Use inherited getter
             this.logger.debug(`[Listener] WebSocketManager status changed: ${status}`);
            // React to WebSocket status changes
            if (status === ConnectionStatus.DISCONNECTED && this.desiredState.connected) {
               this.logger.warn('[Listener] WebSocket disconnected unexpectedly. Attempting recovery.');
               this.attemptRecovery('ws_unexpected_disconnect');
            } else if (status === ConnectionStatus.CONNECTED) {
                this.logger.info('[Listener] WebSocket connected. Resetting resilience.');
                this.resilienceManager.reset(); // Reset failure counts on successful connect
                 // Ensure global app state reflects the connection
                 if (appState.getState().connection.webSocketStatus !== ConnectionStatus.CONNECTED) {
                     appState.updateConnectionState({ webSocketStatus: ConnectionStatus.CONNECTED, isRecovering: false, recoveryAttempt: 0, lastConnectionError: null });
                 }
                this.syncSimulatorState(); // Sync simulator now that connection is up
            } else if (status === ConnectionStatus.DISCONNECTED) {
                // Ensure global app state reflects disconnection
                 if (appState.getState().connection.webSocketStatus !== ConnectionStatus.DISCONNECTED) {
                     this.logger.warn('[Listener] WebSocket transitioned to DISCONNECTED. Updating app state.');
                     // Update state, ensuring recovery flag is false
                     appState.updateConnectionState({ webSocketStatus: ConnectionStatus.DISCONNECTED, isRecovering: false });
                 }
            }
        })
    );
     // Listen for session invalidation messages from the server via WebSocket
     this.wsManager.subscribe('session_invalidated', (data) => {
        if (this.isDisposed) return;
        this.logger.error(`[Listener] Session invalidated by server. Reason: ${data.reason}. Forcing disconnect and logout.`);
        AppErrorHandler.handleAuthError(`Session invalidated: ${data.reason}`, ErrorSeverity.HIGH, 'WebSocketSessionInvalid');
        this.setDesiredState({ connected: false }); // Trigger disconnect flow
        this.emit('auth_failed', { reason: `Session invalidated: ${data.reason}` }); // Notify listeners (e.g., AuthProvider)
     });
     // Note: Other WS message listeners (heartbeat, data) are handled within wsManager or passed up if needed

    // --- ConnectionResilienceManager Listeners ---
    // Listen to resilience events to update global state and potentially log/notify
    this.resilienceManager.subscribe('reconnect_scheduled', (data: any) => {
        if (this.isDisposed) return;
        this.logger.info(`[Listener][Resilience] Reconnection scheduled: attempt ${data.attempt}/${data.maxAttempts} in ${data.delay}ms`);
        // Update global state to indicate recovery is in progress
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
         // Update last error message, state remains isRecovering=true
         appState.updateConnectionState({ lastConnectionError: `Reconnection attempt ${data.attempt} failed.` });
    });
     this.resilienceManager.subscribe('max_attempts_reached', (data: any) => {
         if (this.isDisposed) return;
         const errorMsg = `Failed to reconnect after ${data.maxAttempts} attempts. Check connection or try later.`;
         this.logger.error(`[Listener][Resilience] ${errorMsg}`);
         // Update global state: stop recovering, set error, ensure disconnected status
         appState.updateConnectionState({ isRecovering: false, lastConnectionError: `Failed after ${data.maxAttempts} attempts.`, webSocketStatus: ConnectionStatus.DISCONNECTED });
         // Notify global error handler
         AppErrorHandler.handleConnectionError( errorMsg, ErrorSeverity.HIGH, 'ConnectionResilienceMaxAttempts' );
    });
    this.resilienceManager.subscribe('suspended', (data: any) => {
         if (this.isDisposed) return;
         const suspensionDuration = this.resilienceManager.options.suspensionTimeoutMs / 1000;
         const errorMsg = `Connection attempts suspended for ${suspensionDuration}s after ${data.failureCount} failures.`;
         this.logger.error(`[Listener][Resilience] ${errorMsg}`);
         // Update global state: stop recovering, set error, ensure disconnected status
         appState.updateConnectionState({ isRecovering: false, lastConnectionError: `Connection suspended.`, webSocketStatus: ConnectionStatus.DISCONNECTED });
          // Notify global error handler (medium severity, as it's temporary)
          AppErrorHandler.handleConnectionError(errorMsg, ErrorSeverity.MEDIUM, 'ConnectionSuspended');
    });
    this.resilienceManager.subscribe('resumed', () => {
         if (this.isDisposed) return;
         this.logger.info(`[Listener][Resilience] Connection attempts can resume.`);
         appState.updateConnectionState({ lastConnectionError: null }); // Clear suspension message
         this.syncConnectionState(); // Try to connect again if desired state allows
    });

    // --- Auth State Listener ---
    // Listen to global authentication state changes
    this.subscriptions.add(
        appState.select(state => state.auth).subscribe(authState => {
            if (this.isDisposed) return;
            this.logger.debug(`[Listener] Auth state change: isAuthenticated=${authState.isAuthenticated}, isAuthLoading=${authState.isAuthLoading}`);
            // Inform resilience manager about auth state (it might cancel retries if logged out)
            this.resilienceManager.updateAuthState(authState.isAuthenticated);

            // Only react *after* initial authentication loading is complete
            if (!authState.isAuthLoading) {
                if (authState.isAuthenticated) {
                    // User is authenticated, trigger connection sync to potentially connect
                    this.logger.info('[Listener] Auth confirmed. Triggering connection state sync.');
                    this.syncConnectionState();
                } else {
                    // User is not authenticated, ensure we are disconnected
                    const currentState = appState.getState().connection;
                    if (currentState.webSocketStatus !== ConnectionStatus.DISCONNECTED || currentState.isRecovering) {
                        this.logger.info('[Listener] Authentication lost or absent, ensuring disconnect.');
                        // Setting desired state to false will trigger syncConnectionState -> disconnect
                        this.setDesiredState({ connected: false });
                    } else {
                         this.logger.debug('[Listener] Not authenticated and already disconnected.');
                    }
                }
            }
        })
    );
    this.logger.debug('ConnectionManager event listeners setup complete');
  }

  /**
   * Updates the desired connection/simulator state and triggers synchronization.
   * @param state - A partial state object indicating the desired status.
   */
  public setDesiredState(state: Partial<ConnectionDesiredState>): void {
    // *** TEMPORARY LOG ***
    console.log(`*** ConnectionManager: setDesiredState called with: ${JSON.stringify(state)} ***`);
    if (this.isDisposed) {
      this.logger.error('Cannot set desired state: ConnectionManager is disposed');
      return;
    }
    this.logger.info(`Setting desired state: ${JSON.stringify(state)}`);

    // Check if the requested state is actually different from the current desired state
    const changed = Object.keys(state).some(
        key => this.desiredState[key as keyof ConnectionDesiredState] !== state[key as keyof ConnectionDesiredState]
    );
    if (!changed) {
        this.logger.debug('Desired state unchanged, skipping sync.');
        return; // No change, no need to sync
    }

    // Update the internal desired state
    const oldState = { ...this.desiredState };
    this.desiredState = { ...this.desiredState, ...state };
    this.logger.info('Desired state updated', { oldState, newState: this.desiredState });

    // Trigger synchronization methods
    this.logger.debug('Triggering state sync after desired state change.');
    this.syncConnectionState(); // Sync WebSocket connection
    this.syncSimulatorState(); // Sync simulator status
  }

  /**
   * Attempts to align the actual WebSocket connection state with the desired state.
   * Considers authentication status and resilience state.
   */
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

    // Get current states needed for decision making
    const currentAuthState = appState.getState().auth;
    const resilienceInfo = this.resilienceManager.getState();

    // *** Log states (changed to WARN for visibility during debug) ***
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

    // Get current connection status details
    const currentConnState = appState.getState().connection;
    const isConnected = currentConnState.webSocketStatus === ConnectionStatus.CONNECTED;
    const isConnecting = currentConnState.webSocketStatus === ConnectionStatus.CONNECTING;
    const isRecovering = currentConnState.isRecovering;

    this.logger.debug(`syncConnectionState - Connection Vars: Desired=${this.desiredState.connected}, isConnected=${isConnected}, isConnecting=${isConnecting}, isRecovering=${isRecovering}`);
    // Log check variables
    console.log(`*** syncConnectionState Check Values: desired.connected=${this.desiredState.connected}, !isConnected=${!isConnected}, !isConnecting=${!isConnecting}, !isRecovering=${!isRecovering} ***`);

    // --- GUARD 4: Check if trying to connect but not authenticated ---
    // This is a safety check; the auth listener should prevent this state mostly.
    if (this.desiredState.connected && !currentAuthState.isAuthenticated) {
        console.log('*** syncConnectionState EXITING due to guard: NOT AUTHENTICATED (Guard 4) ***');
        this.logger.warn('syncConnectionState decision: Cannot connect, user not authenticated.');
        // If somehow connected/connecting/recovering while not authenticated, force disconnect
        if (isConnected || isConnecting || isRecovering) {
           this.disconnect('not_authenticated_sync');
        }
        return; // Exit
    }

    // --- The Decision Logic ---
    // Condition to Connect: Desired=true, Authenticated=true, Not already connected/connecting/recovering
    if (this.desiredState.connected && !isConnected && !isConnecting && !isRecovering) {
      this.logger.info('syncConnectionState decision: Attempting connect.');
      console.log('*** ConnectionManager: syncConnectionState - DECISION: Connect ***');
      // Initiate connection process (handles session validation + WS connect)
      this.connect().catch(err => {
        // Log error if the connect promise rejects (errors within connect are logged there too)
        this.logger.error('syncConnectionState: Connect promise rejected', { error: err instanceof Error ? err.message : String(err) });
      });
    }
    // Condition to Disconnect: Desired=false, Currently connected/connecting/recovering
    else if (!this.desiredState.connected && (isConnected || isConnecting || isRecovering)) {
      this.logger.info('syncConnectionState decision: Attempting disconnect.');
      console.log('*** ConnectionManager: syncConnectionState - DECISION: Disconnect ***');
      this.disconnect('desired_state_false_sync'); // Trigger disconnection
    }
    // Condition for No Action: State matches desire or other conditions not met
    else {
      this.logger.debug('syncConnectionState decision: No action needed.');
      console.log('*** ConnectionManager: syncConnectionState - DECISION: No Action ***');
    }
  }

  /**
   * Attempts to align the actual simulator state with the desired state.
   * Only acts if the WebSocket connection is established.
   */
  private async syncSimulatorState(): Promise<void> {
     if (this.isDisposed) return; // Check if disposed

     const currentConnState = appState.getState().connection;
     // Only sync simulator if WebSocket is actually connected
     if (currentConnState.webSocketStatus !== ConnectionStatus.CONNECTED) {
         this.logger.debug('Sync simulator state skipped: Not connected.');
         return;
     }

     // Get current simulator status and desired state
     const currentSimStatus = currentConnState.simulatorStatus;
     const isRunning = currentSimStatus === 'RUNNING';
     const isBusy = currentSimStatus === 'STARTING' || currentSimStatus === 'STOPPING'; // Busy transitioning

     // Logic: Start if desired=true, not running, and not busy. Stop if desired=false, running, and not busy.
     if (this.desiredState.simulatorRunning && !isRunning && !isBusy) {
         this.logger.info('Syncing simulator state: attempting to start simulator');
         await this.startSimulator(); // Call action method
     }
     else if (!this.desiredState.simulatorRunning && isRunning && !isBusy) {
         this.logger.info('Syncing simulator state: stopping simulator');
         await this.stopSimulator(); // Call action method
     }
     else {
         // Log why no action is taken if needed
         this.logger.debug('Sync simulator state: No action needed.', { desired: this.desiredState.simulatorRunning, currentStatus: currentSimStatus, isBusy });
     }
   }

  /**
   * Initiates the connection process: validates session, then connects WebSocket.
   * Handles errors and triggers recovery if necessary.
   * @returns {Promise<boolean>} True if connection process initiated successfully, false otherwise.
   */
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
     // Prevent concurrent connection attempts or connecting when already connected
     if (currentConnState.webSocketStatus === ConnectionStatus.CONNECTING || currentConnState.webSocketStatus === ConnectionStatus.CONNECTED) { this.logger.warn(`connect() ignored: Status=${currentConnState.webSocketStatus}`); return currentConnState.webSocketStatus === ConnectionStatus.CONNECTED; }
     // Prevent connection if recovering or resilience manager blocks it
     if (currentConnState.isRecovering || resilienceInfo.state === 'suspended' || resilienceInfo.state === 'failed') { this.logger.warn(`connect() ignored: Recovering or Resilience=${resilienceInfo.state}.`); return false; }
     // --- End Guards ---

    // Wrap the core logic in a timed block for performance monitoring
    return this.logger.trackTime('connect_process', async () => {
      // Re-check guards within async block
      if (this.isDisposed) return false;
      if (!this.tokenManager.isAuthenticated()) { this.logger.error('connect() aborted: Not authenticated (re-check)'); appState.updateConnectionState({ webSocketStatus: ConnectionStatus.DISCONNECTED, lastConnectionError: 'Auth required' }); return false; }

      this.logger.info('connect(): Attempting connection process...');
      // Update global state to show connection attempt is starting
      appState.updateConnectionState({ webSocketStatus: ConnectionStatus.CONNECTING, lastConnectionError: null, isRecovering: false });

      let sessionOk = false;
      let wsOk = false;
      try {
        // 1. Validate Session via HTTP API
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
        sessionOk = true; // Mark session validation as successful

        // 2. Connect WebSocket via WebSocketManager
        this.logger.debug('connect(): Connecting WebSocket via wsManager...');
        console.log('*** CM: connect - BEFORE wsManager.connect() ***');
        wsOk = await this.wsManager.connect(); // Delegate actual WS connection
        console.log(`*** CM: connect - AFTER wsManager.connect(), result: ${wsOk} ***`);
        if (this.isDisposed) { if (wsOk) this.wsManager.disconnect('disposed_during_connect'); return false; } // Check again

        // Check if WebSocket connection was successful
        if (!wsOk) {
           this.logger.error('connect(): wsManager.connect() returned false (connection failed).');
           // Ensure state reflects failure if wsManager didn't trigger listener update yet
           if (!appState.getState().connection.lastConnectionError) { appState.updateConnectionState({ lastConnectionError: 'WebSocket connection failed', webSocketStatus: ConnectionStatus.DISCONNECTED }); }
           // Record failure and attempt recovery
           this.resilienceManager.recordFailure('WebSocket failed post-session');
           this.attemptRecovery('ws_connect_failed_post_session');
           return false; // Indicate connection failure
        }

        // If wsOk is true, wsManager listener should handle state update to CONNECTED
        this.logger.info('connect(): Connection process initiated successfully (WebSocket connecting/connected).');
        return true; // Indicate successful initiation

      } catch (error: any) {
        // Catch errors from session validation or wsManager.connect
        console.error(`*** CM: connect - ERROR caught in process: ${error?.message} ***`, error);
        if (this.isDisposed) return false;
        const errorMessage = error instanceof Error ? error.message : String(error);
        this.logger.error(`connect(): Connection process failed during ${sessionOk ? 'WebSocket phase' : 'session validation phase'}.`, { error: errorMessage });
        // Set state to disconnected on any error during the process
        appState.updateConnectionState({ webSocketStatus: ConnectionStatus.DISCONNECTED, isRecovering: false, lastConnectionError: errorMessage });
        // Record failure and attempt recovery
        this.resilienceManager.recordFailure(`Connection process error: ${errorMessage}`);
        this.attemptRecovery('connect_process_exception');
        // Notify global error handler
        AppErrorHandler.handleConnectionError(errorMessage, ErrorSeverity.HIGH, 'ConnectionManager.connect');
        return false; // Indicate connection failure
      }
    });
  }

  /**
   * Disconnects the WebSocket connection and resets resilience state.
   * @param reason - A string indicating the reason for disconnection.
   */
  public disconnect(reason: string = 'manual_disconnect'): void {
    this.logger.info(`disconnect() called. Reason: ${reason}`);
    if (this.isDisposed && reason !== 'manager_disposed') { this.logger.debug(`Disconnect ignored: Disposed.`); return; }

     // Check if already disconnected or not trying to connect/recover
     const currentState = appState.getState().connection;
     const wasConnectedOrConnecting = currentState.webSocketStatus !== ConnectionStatus.DISCONNECTED || currentState.isRecovering;
     if (!wasConnectedOrConnecting) {
         this.logger.debug(`Disconnect ignored: Already disconnected.`);
         return;
     }

     this.logger.warn(`Disconnecting internal state. Reason: ${reason}`);
     this.resilienceManager.reset(); // Reset failure counts and timers
     this.wsManager.disconnect(reason); // Tell WebSocketManager to close the socket

     // Immediately update app state to reflect disconnection
     appState.updateConnectionState({
         webSocketStatus: ConnectionStatus.DISCONNECTED,
         isRecovering: false, // Ensure recovery is off
         quality: ConnectionQuality.UNKNOWN, // Reset quality metrics
         heartbeatLatency: null,
         lastHeartbeatTime: undefined,
         lastConnectionError: `Disconnected: ${reason}`,
         // Reset simulator status if it wasn't already stopped/unknown
         ...(currentState.simulatorStatus !== 'STOPPED' && currentState.simulatorStatus !== 'UNKNOWN' && { simulatorStatus: 'UNKNOWN' })
     });
  }

  /**
   * Initiates the connection recovery process via the resilience manager.
   * Checks auth status and resilience state before attempting.
   * @param reason - A string indicating the reason for attempting recovery.
   * @returns {Promise<boolean>} True if recovery attempt was successfully initiated, false otherwise.
   */
   public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
     this.logger.info(`attemptRecovery() called. Reason: ${reason}`);
     if (this.isDisposed) { this.logger.debug('Recovery aborted: Disposed.'); return false; }

     // --- Guards ---
     const currentAuthState = appState.getState().auth;
     if (currentAuthState.isAuthLoading) { this.logger.warn(`Recovery ignored: Auth loading.`); return false; }
     if (!currentAuthState.isAuthenticated) { this.logger.warn(`Recovery ignored: Not authenticated.`); return false; }
     const resilienceInfo = this.resilienceManager.getState();
     const currentConnState = appState.getState().connection;
     // Don't attempt recovery if already recovering, suspended, or failed
     if (currentConnState.isRecovering || resilienceInfo.state === 'suspended' || resilienceInfo.state === 'failed') { this.logger.warn(`Recovery ignored: Already recovering or Resilience=${resilienceInfo.state}.`); return false; }
     // --- End Guards ---

     this.logger.warn(`Connection recovery requested via resilience manager. Reason: ${reason}`);
     // Optimistically update state to show recovery starting
     // Use resilience attempt count + 1 for the next attempt number
     appState.updateConnectionState({ isRecovering: true, recoveryAttempt: resilienceInfo.attempt + 1 });

     // Delegate the actual retry scheduling and execution to the resilience manager
     const initiated = await this.resilienceManager.attemptReconnection(() => this.connect());

     // Handle case where resilience manager couldn't initiate (e.g., max attempts reached internally)
     if (!initiated && !this.isDisposed) {
          this.logger.warn("Recovery could not be initiated by resilience manager (check its internal state/logs).");
           // Revert optimistic state if recovery didn't actually start
           if(appState.getState().connection.isRecovering) {
              appState.updateConnectionState({ isRecovering: false, recoveryAttempt: 0 });
           }
      } else if (initiated) {
          this.logger.info("Recovery process initiated by resilience manager.");
      }
     return initiated; // Return whether the resilience manager started the process
   }

  // --- Public Actions ---
  // These methods act as a public facade, performing checks before calling handlers

  /** Submits a trading order after checking connection and simulator status. */
  public async submitOrder(order: SubmitOrderRequest): Promise<SubmitOrderResult> {
      if (this.isDisposed) return { success: false, error: 'CM disposed' };
      const state = appState.getState().connection;
      // Check if connected
      if (state.webSocketStatus !== ConnectionStatus.CONNECTED) {
          const e = 'Submit order failed: Not connected';
          AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'SubmitOrderCheck');
          return { success: false, error: e };
      }
      // Check if simulator is running
      if (state.simulatorStatus !== 'RUNNING') {
          const e = 'Submit order failed: Simulator not running';
          AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'SubmitOrderCheck');
          return { success: false, error: e };
      }
      this.logger.info('Submitting order', { symbol: order.symbol, type: order.type, side: order.side });
      // Delegate to data handler
      return this.dataHandlers.submitOrder(order);
  }

  /** Cancels a trading order after checking connection and simulator status. */
  public async cancelOrder(orderId: string): Promise<CancelOrderResult> {
      if (this.isDisposed) return { success: false, error: 'CM disposed' };
      const state = appState.getState().connection;
      if (state.webSocketStatus !== ConnectionStatus.CONNECTED) { const e = 'Cancel order failed: Not connected'; AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'CancelOrderCheck'); return { success: false, error: e }; }
      if (state.simulatorStatus !== 'RUNNING') { const e = 'Cancel order failed: Simulator not running'; AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'CancelOrderCheck'); return { success: false, error: e }; }
      this.logger.info('Cancelling order', { orderId });
      // Delegate to data handler
      return this.dataHandlers.cancelOrder(orderId);
  }

  /** Starts the simulator after checking connection status. */
  public async startSimulator(): Promise<SimulatorActionResult> {
      if (this.isDisposed) return { success: false, error: 'CM disposed' };
      this.desiredState.simulatorRunning = true; // Set intent
      const state = appState.getState().connection;
      if (state.webSocketStatus !== ConnectionStatus.CONNECTED) { const e = 'Start simulator failed: Not connected'; return { success: false, error: e }; }
      // Prevent starting if already running or starting
      if (state.simulatorStatus === 'RUNNING' || state.simulatorStatus === 'STARTING') { this.logger.warn(`Start sim ignored: Status=${state.simulatorStatus}`); return { success: true, status: state.simulatorStatus }; }

      this.logger.info('Starting simulator...');
      appState.updateConnectionState({ simulatorStatus: 'STARTING' }); // Optimistic UI update
      try {
          const result = await this.simulatorManager.startSimulator(); // Call API
          if (this.isDisposed) return { success: false, error: 'Disposed' };
          // Update state based on API response
          appState.updateConnectionState({ simulatorStatus: result.success ? (result.status || 'RUNNING') : 'ERROR', lastConnectionError: result.success ? null : (result.errorMessage || 'Failed start') });
          if (!result.success) {
              this.desiredState.simulatorRunning = false; // Revert intent on failure
              AppErrorHandler.handleGenericError(result.errorMessage || 'Failed start', ErrorSeverity.MEDIUM, 'StartSim');
          }
          return { success: result.success, status: result.status, error: result.errorMessage };
      } catch (error: any) {
          // Handle exceptions during API call
          if (this.isDisposed) return { success: false, error: 'Disposed' };
          const e = error instanceof Error ? error.message : String(error);
          this.logger.error('Error starting sim', { error: e });
          appState.updateConnectionState({ simulatorStatus: 'ERROR', lastConnectionError: e });
          this.desiredState.simulatorRunning = false; // Revert intent on exception
          AppErrorHandler.handleGenericError(e, ErrorSeverity.HIGH, 'StartSimEx');
          return { success: false, error: e };
      }
  }

  /** Stops the simulator after checking connection status. */
   public async stopSimulator(): Promise<SimulatorActionResult> {
       if (this.isDisposed) return { success: false, error: 'CM disposed' };
       this.desiredState.simulatorRunning = false; // Set intent
       const state = appState.getState().connection;
       if (state.webSocketStatus !== ConnectionStatus.CONNECTED) { const e = 'Stop simulator failed: Not connected'; return { success: false, error: e }; }
       // Prevent stopping if already stopped/stopping or not running/starting
       if (state.simulatorStatus !== 'RUNNING' && state.simulatorStatus !== 'STARTING') { this.logger.warn(`Stop sim ignored: Status=${state.simulatorStatus}`); return { success: true, status: state.simulatorStatus }; }

       this.logger.info('Stopping simulator...');
       appState.updateConnectionState({ simulatorStatus: 'STOPPING' }); // Optimistic UI update
       try {
           const r = await this.simulatorManager.stopSimulator(); // Call API
           if (this.isDisposed) return { success: false, error: 'Disposed' };
           // Update state based on API response
           const status = r.success ? 'STOPPED' : 'ERROR';
           const errorMsg = r.success ? null : (r.errorMessage || 'Failed stop');
           appState.updateConnectionState({ simulatorStatus: status, lastConnectionError: errorMsg });
           if (!r.success) {
                // Don't revert desiredState on stop failure, maybe log/notify
                AppErrorHandler.handleGenericError(errorMsg || 'Failed stop', ErrorSeverity.MEDIUM, 'StopSim');
           }
           // *** FIX: Use 'r' variable consistently ***
           return { success: r.success, status: r.status, error: r.errorMessage };
       } catch (error: any) {
            // Handle exceptions during API call
           if (this.isDisposed) return { success: false, error: 'Disposed' };
           const e = error instanceof Error ? error.message : String(error);
           this.logger.error('Error stopping sim', { error: e });
           appState.updateConnectionState({ simulatorStatus: 'ERROR', lastConnectionError: e });
           // Don't revert desiredState on stop failure
           AppErrorHandler.handleGenericError(e, ErrorSeverity.HIGH, 'StopSimEx');
           return { success: false, error: e };
       }
   }

   /** Initiates a manual reconnection attempt. */
   public manualReconnect(): void {
     this.logger.warn('Manual reconnect triggered via manualReconnect()');
     if (this.isDisposed) return;
     this.setDesiredState({ connected: true }); // Set desire to connect
     this.attemptRecovery('manual_user_request'); // Start recovery process
  }

  // --- Dispose ---
  /** Cleans up resources, subscriptions, and disconnects. */
  public override dispose(): void {
       if (this.isDisposed) return; // Prevent double disposal
       this.logger.warn('Disposing ConnectionManager...');
       this.disconnect('manager_disposed'); // Ensure disconnected state
       // Dispose managed instances if they have dispose methods
       if (this.resilienceManager?.dispose) this.resilienceManager.dispose();
       if (this.wsManager?.dispose) this.wsManager.dispose();
       // Unsubscribe from all RxJS subscriptions
       this.subscriptions.unsubscribe();
       // Call base class dispose for event emitter cleanup
       super.dispose();
       this.logger.info('ConnectionManager disposed.');
   }

  // Support for 'using' statement if needed
  [Symbol.dispose](): void {
    this.dispose();
  }
} // End of ConnectionManager class
