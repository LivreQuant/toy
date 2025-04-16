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
import { DeviceIdManager } from '../auth/device-id-manager';
import { OrderSide, OrderType, SubmitOrderRequest, SubmitOrderResponse } from '../../api/order';
import { SimulatorStatusResponse } from '../../api/simulator';
import { EnhancedLogger } from '../../utils/enhanced-logger';
import { getLogger } from '../../boot/logging';
import { TypedEventEmitter } from '../../utils/typed-event-emitter';
import { firstValueFrom } from 'rxjs';

// Define events emitted by this manager
export interface ConnectionManagerEvents {
  auth_failed: { reason: string };
  device_id_changed: { oldDeviceId: string, newDeviceId: string };
  device_id_invalidated: { deviceId: string, reason?: string }; // Add this line
}


// Define the desired state structure
export interface ConnectionDesiredState {
  connected: boolean;
  simulatorRunning: boolean;
}

// Define options for configuring the manager
export interface ConnectionManagerOptions {
  wsOptions?: WebSocketOptions;
  wsManager?: WebSocketManager; // Added to support direct instance passing
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
    const loggerInstance = getLogger('ConnectionManager');
    // Call super() ONCE before using 'this'
    super(loggerInstance);
    // Assign logger to the instance property
    this.logger = loggerInstance;
  
    this.logger.info('ConnectionManager initializing...', { options });
  
    // --- Service Instantiation ---
    this.tokenManager = tokenManager;
    this.httpClient = new HttpClient(tokenManager); // Used by other API clients
    
    // WebSocket Manager setup - use provided instance or create new one
    this.wsManager = options.wsManager || new WebSocketManager(
      tokenManager,
      { ...options.wsOptions, preventAutoConnect: true } // Ensure CM controls connections
    );
    
    // Initialize APIs with the WebSocket manager
    this.sessionApi = new SessionApi(this.wsManager);
    this.dataHandlers = new ConnectionDataHandlers(this.httpClient); // For orders etc.
    this.simulatorManager = new ConnectionSimulatorManager(this.wsManager);
    
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
        console.error('🚨 CONNECTION STATUS CHANGE 🚨', {
          status,
          desiredState: this.desiredState,
          currentAuthState: {
            isAuthenticated: appState.getState().auth.isAuthenticated,
            isAuthLoading: appState.getState().auth.isAuthLoading
          },
          connectionState: appState.getState().connection,
          stackTrace: new Error().stack?.split('\n').slice(1, 10).join('\n'),
          timestamp: new Date().toISOString()
        });
  
        // Original logic remains the same
        if (this.isDisposed) return;
  
        // Add explicit logging for each condition
        if (status === ConnectionStatus.DISCONNECTED && this.desiredState.connected) {
          console.error('💥 UNEXPECTED DISCONNECT - ATTEMPTING RECOVERY', {
            reason: 'WebSocket disconnected unexpectedly',
            stackTrace: new Error().stack?.split('\n').slice(1, 10).join('\n')
          });
          this.attemptRecovery('ws_unexpected_disconnect');
        } else if (status === ConnectionStatus.CONNECTED) {
              this.logger.info('[Listener] WebSocket connected. Resetting resilience.');
              this.resilienceManager.reset();
              if (appState.getState().connection.webSocketStatus !== ConnectionStatus.CONNECTED) {
                  appState.updateConnectionState({ webSocketStatus: ConnectionStatus.CONNECTED, isRecovering: false, recoveryAttempt: 0, lastConnectionError: null });
              }
              this.syncSimulatorState();
          } else if (status === ConnectionStatus.DISCONNECTED) {
              if (appState.getState().connection.webSocketStatus !== ConnectionStatus.DISCONNECTED) {
                  this.logger.warn('[Listener] WebSocket transitioned to DISCONNECTED. Updating app state.');
                  appState.updateConnectionState({ webSocketStatus: ConnectionStatus.DISCONNECTED, isRecovering: false });
              }
          }
      })
    );
    
    // Listen for device ID invalidation events
    this.wsManager.on('device_id_invalidated').subscribe(data => {
      if (this.isDisposed) return;
      this.logger.warn(`[Listener] Device ID invalidated: ${data.deviceId}. Reason: ${data.reason}`);
      
      // Clear the device ID in DeviceIdManager
      DeviceIdManager.getInstance().clearDeviceId();
      
      // Force disconnect
      this.disconnect('device_id_invalidated');
      
      // Emit event for other components
      this.emit('device_id_invalidated', {
        deviceId: data.deviceId,
        reason: data.reason
      });
      
      // Update app state with a special flag to trigger redirect
      appState.updateAuthState({
        isAuthenticated: true, // Keep authenticated but with invalid device
        isAuthLoading: false,
        lastAuthError: `Device ID invalidated: ${data.reason}`
      });
    });
    
    // Listen for session invalidation messages from the server via WebSocket
    this.wsManager.subscribe('heartbeat_ack', (data) => {
        if (this.isDisposed) return;
        
        // Update simulator status if provided
        if (data.simulatorStatus) {
            appState.updateConnectionState({ 
                simulatorStatus: data.simulatorStatus 
            });
        }
        
        // If session is invalid according to server, handle logout
        if (data.sessionStatus === 'invalid') {
            this.logger.error(`[Listener] Session invalidated by heartbeat response. Forcing disconnect and logout.`);
            AppErrorHandler.handleAuthError(`Session invalidated by server`, ErrorSeverity.HIGH, 'HeartbeatSessionInvalid');
            this.setDesiredState({ connected: false });
            this.emit('auth_failed', { reason: `Session invalidated by server` });
            
            // Clear tokens
            //this.tokenManager.clearTokens();
            
            // Update auth state
            appState.updateAuthState({
                isAuthenticated: false,
                isAuthLoading: false,
                userId: null,
                lastAuthError: 'Session invalidated by server'
            });
        }
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
    });
    
    this.resilienceManager.subscribe('reconnect_failure', (data: any) => {
        if (this.isDisposed) return;
        this.logger.warn(`[Listener][Resilience] Reconnection attempt ${data.attempt} failed`);
        appState.updateConnectionState({ lastConnectionError: `Reconnection attempt ${data.attempt} failed.` });
    });
    
    this.resilienceManager.subscribe('max_attempts_reached', (data: any) => {
        if (this.isDisposed) return;
        const errorMsg = `Failed to reconnect after ${data.maxAttempts} attempts. Check connection or try later.`;
        this.logger.error(`[Listener][Resilience] ${errorMsg}`);
        appState.updateConnectionState({ isRecovering: false, lastConnectionError: `Failed after ${data.maxAttempts} attempts.`, webSocketStatus: ConnectionStatus.DISCONNECTED });
        AppErrorHandler.handleConnectionError(errorMsg, ErrorSeverity.HIGH, 'ConnectionResilienceMaxAttempts');
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
        appState.updateConnectionState({ lastConnectionError: null });
        this.syncConnectionState();
    });

    // --- Auth State Listener ---
    this.subscriptions.add(
      appState.select(state => state.auth).subscribe(authState => {
        if (this.isDisposed) return;
        
        this.logger.info(`[Listener] AUTH STATE CHANGE: isAuthLoading=${authState.isAuthLoading}, isAuthenticated=${authState.isAuthenticated}`);
        
        // Skip if auth is still loading
        if (authState.isAuthLoading) {
          this.logger.debug('Auth state is still loading, skipping action');
          return;
        }
        
        // Inform resilience manager about auth state
        this.resilienceManager.updateAuthState(authState.isAuthenticated);
    
        if (authState.isAuthenticated) {
          // User is authenticated - set desired state to connected and trigger sync
          this.desiredState.connected = true; // Set directly for immediate effect
          this.syncConnectionState(); // Trigger connection sync
        } else {
          // User is not authenticated - ensure disconnection
          this.setDesiredState({ connected: false }); // Will trigger disconnect
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
    
    this.syncConnectionState(); // No arguments
    
    // If simulator desire changed, sync simulator state
    if (oldState.simulatorRunning !== this.desiredState.simulatorRunning) {
        this.syncSimulatorState(); // Sync simulator status
    }
  }

  /**
   * Attempts to align the actual WebSocket connection state with the desired state.
   * Considers resilience state and authentication status.
   */
  private syncConnectionState(): void {
    this.logger.warn('Sync Connection State - Detailed Diagnostic', {
      desiredState: this.desiredState,
      currentAuthState: {
        isAuthenticated: appState.getState().auth.isAuthenticated,
        isAuthLoading: appState.getState().auth.isAuthLoading,
        userId: appState.getState().auth.userId
      },
      currentConnectionState: appState.getState().connection,
      resilienceManagerState: this.resilienceManager.getState(),
      timestamp: new Date().toISOString()
    });

    // --- GUARD 1: Check if disposed ---
    if (this.isDisposed) {
      return;
    }
  
    // Get current states needed for decision making
    const currentAuthState = appState.getState().auth;
    const resilienceInfo = this.resilienceManager.getState();
  
    // --- GUARD 2: Check if auth is still loading ---
    if (currentAuthState.isAuthLoading) {
      this.logger.debug('syncConnectionState skipped: Authentication is loading.');
      return;
    }
    
    // --- GUARD 3: Check if not authenticated ---
    if (!currentAuthState.isAuthenticated) {
      this.logger.warn('syncConnectionState skipped: User not authenticated.');
      return;
    }
    
    // --- GUARD 4: Check if resilience manager is preventing connections ---
    if (resilienceInfo.state === 'suspended' || resilienceInfo.state === 'failed') {
      this.logger.warn(`syncConnectionState skipped: Resilience state is ${resilienceInfo.state}.`);
      return;
    }
  
    // Get current connection status details
    const currentConnState = appState.getState().connection;
    const isConnected = currentConnState.webSocketStatus === ConnectionStatus.CONNECTED;
    const isConnecting = currentConnState.webSocketStatus === ConnectionStatus.CONNECTING;
    const isRecovering = currentConnState.isRecovering;
  
    this.logger.debug(`syncConnectionState - Connection Vars: Desired=${this.desiredState.connected}, isConnected=${isConnected}, isConnecting=${isConnecting}, isRecovering=${isRecovering}`);
  
    // --- The Decision Logic ---
    // Condition to Connect: Desired=true, Authenticated=true, Not already connected/connecting/recovering
    if (this.desiredState.connected && !isConnected && !isConnecting && !isRecovering) {
      this.logger.info('syncConnectionState decision: Attempting connect.');
      // Initiate connection process (handles session validation + WS connect)
      this.connect().catch(err => {
        // Log error if the connect promise rejects (errors within connect are logged there too)
        this.logger.error('syncConnectionState: Connect promise rejected', { error: err instanceof Error ? err.message : String(err) });
      });
    }
    // Condition to Disconnect: Desired=false, Currently connected/connecting/recovering
    else if (!this.desiredState.connected && (isConnected || isConnecting || isRecovering)) {
      this.logger.info('syncConnectionState decision: Attempting disconnect.');
      this.disconnect('desired_state_false_sync'); // Trigger disconnection
    }
    // Condition for No Action: State matches desire or other conditions not met
    else {
      this.logger.debug('syncConnectionState decision: No action needed.');
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
         this.logger.debug('Sync sim state skipped: Not connected.');
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
    this.logger.warn('Connect method called', {
      desiredState: this.desiredState,
      // Use wsManager's connection status method instead
      currentConnectionStatus: await firstValueFrom(this.wsManager.getConnectionStatus())
    });

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
      appState.updateConnectionState({
        webSocketStatus: ConnectionStatus.CONNECTED,
        lastConnectionError: null,
        simulatorStatus: 'NONE'  // Based on the session info
      });

      let sessionOk = false;
      let wsOk = false;
      try {
        // 1. First, Connect WebSocket via WebSocketManager
        this.logger.debug('connect(): Connecting WebSocket first...');
        const wsOk = await this.wsManager.connect(); // Delegate actual WS connection
        if (this.isDisposed) { if (wsOk) this.wsManager.disconnect('disposed_during_connect'); return false; }
  
        // Check if WebSocket connection was successful
        if (!wsOk) {
          this.logger.error('connect(): wsManager.connect() returned false (connection failed).');
          // ... existing error handling ...
          return false;
        }
  
        // 2. Then, validate Session via WebSocket only after WS is connected
        this.logger.debug('connect(): WebSocket connected, now validating session...');
        const sessionResponse = await this.sessionApi.createSession();
        if (this.isDisposed) return false; // Check again after await
        
        if (!sessionResponse.success) {
          this.logger.error('connect(): Session validation failed.', { error: sessionResponse.errorMessage });
          throw new Error(`Session Error: ${sessionResponse.errorMessage || 'Failed session validation'}`);
        }
        
        this.logger.info('connect(): Session validated successfully.');
        
        // Connection and session validation successful
        this.logger.info('connect(): Connection process completed successfully.');
        return true;
  
      } catch (error: any) {
        // Catch errors from session validation or potentially wsManager.connect if it throws
        if (this.isDisposed) return false;
        const errorMessage = error instanceof Error ? error.message : String(error);
        this.logger.error(`connect(): Connection process failed during ${sessionOk ? 'WebSocket phase' : 'session validation phase'}.`, { error: errorMessage });
        // Set state to disconnected on any error during the process
          
        // Ensure disconnected state is set
        appState.updateConnectionState({
          webSocketStatus: ConnectionStatus.DISCONNECTED,
          lastConnectionError: error instanceof Error ? error.message : String(error)
        });

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
  public async disconnect(reason: string = 'manual_disconnect'): Promise<boolean> {
    this.logger.info(`disconnect() called. Reason: ${reason}`);
    if (this.isDisposed && reason !== 'manager_disposed') { this.logger.debug(`Disconnect ignored: Disposed.`); return true; }

     // Check if already disconnected or not trying to connect/recover
     const currentState = appState.getState().connection;
     const wasConnectedOrConnecting = currentState.webSocketStatus !== ConnectionStatus.DISCONNECTED || currentState.isRecovering;
     if (!wasConnectedOrConnecting) {
         this.logger.debug(`Disconnect ignored: Already disconnected.`);
         return true;
     }

     try {
      this.logger.info('Requesting session stop via SessionAPI...');
      // Use the sessionApi instance to request session termination
      const response = await this.sessionApi.deleteSession();
      
      if (response.success) {
        this.logger.info('Session stop request successful');
        
        // Update app state to reflect stopped simulator
        appState.updateConnectionState({
          simulatorStatus: 'STOPPED'
        });
        
        // Clear desired state for simulator
        this.desiredState.simulatorRunning = false;
        
      } else {
        this.logger.warn('Session stop request failed:', { error: response.errorMessage });
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

      return true;
    } catch (error: any) {
      this.logger.error('Exception during session stop request:', { 
        error: error instanceof Error ? error.message : String(error) 
      });
      return false;
    }
  }

  /**
   * Initiates the connection recovery process via the resilience manager.
   * Checks auth status and resilience state before attempting.
   * @param reason - A string indicating the reason for attempting recovery.
   * @returns {Promise<boolean>} True if recovery attempt was successfully initiated, false otherwise.
   */
   public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    this.logger.error('Attempt Recovery Triggered', {
      reason,
      currentAuthState: appState.getState().auth,
      currentConnectionState: appState.getState().connection,
      desiredState: this.desiredState,
      resilienceState: this.resilienceManager.getState()
    });
  
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
     // continued from connection-manager.ts
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

  /**
   * Manually initiates a reconnection process using the WebSocket reconnect message
   * if connected, or through the connect process if disconnected.
   * @returns {Promise<boolean>} True if reconnection was successfully initiated, false otherwise.
   */
  public async manualReconnect(): Promise<boolean> {
    this.logger.warn('Manual reconnect triggered via manualReconnect()');
    if (this.isDisposed) return false;
    
    // Set desire to connect
    this.setDesiredState({ connected: true });
    
    // Use firstValueFrom to get the current value from the observable
    const currentStatus = await firstValueFrom(this.wsManager.getConnectionStatus());
    
    // If WebSocket is open, try to send reconnect message directly
    if (this.wsManager && currentStatus === ConnectionStatus.CONNECTED) {
      this.logger.info('WebSocket is open, sending reconnect message');
      return this.wsManager.sendReconnect();
    } else {
      // Otherwise start recovery process
      this.logger.info('WebSocket not connected, starting recovery process');
      return this.attemptRecovery('manual_user_request');
    }
  }

  // --- Public Actions ---
  // These methods act as a public facade, performing checks before calling handlers

  /** Submits a trading order after checking connection and simulator status. */
  public async submitOrder(order: SubmitOrderRequest): Promise<SubmitOrderResult> {
      if (this.isDisposed) return { success: false, error: 'CM disposed' };
      const state = appState.getState().connection;
      // Check if connected
      if (state.webSocketStatus !== ConnectionStatus.CONNECTED) { const e = 'Submit order failed: Not connected'; AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'SubmitOrderCheck'); return { success: false, error: e }; }
      // Check if simulator is running
      if (state.simulatorStatus !== 'RUNNING') { const e = 'Submit order failed: Simulator not running'; AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'SubmitOrderCheck'); return { success: false, error: e }; }
      this.logger.info('Submitting order',{symbol: order.symbol, type: order.type, side: order.side});
      // Delegate to data handler
      return this.dataHandlers.submitOrder(order);
  }

  /** Cancels a trading order after checking connection and simulator status. */
  public async cancelOrder(orderId: string): Promise<CancelOrderResult> {
      if (this.isDisposed) return { success: false, error: 'CM disposed' };
      const state = appState.getState().connection;
      if (state.webSocketStatus !== ConnectionStatus.CONNECTED) { const e = 'Cancel order failed: Not connected'; AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'CancelOrderCheck'); return { success: false, error: e }; }
      if (state.simulatorStatus !== 'RUNNING') { const e = 'Cancel order failed: Simulator not running'; AppErrorHandler.handleGenericError(e, ErrorSeverity.MEDIUM, 'CancelOrderCheck'); return { success: false, error: e }; }
      this.logger.info('Cancelling order',{orderId});
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
          const r = await this.simulatorManager.startSimulator(); // Call API
          if (this.isDisposed) return { success: false, error: 'Disposed' };
          // Update state based on API response
          appState.updateConnectionState({ simulatorStatus: r.success ? (r.status || 'RUNNING') : 'ERROR', lastConnectionError: r.success ? null : (r.errorMessage || 'Failed start') });
          if (!r.success) { this.desiredState.simulatorRunning = false; AppErrorHandler.handleGenericError(r.errorMessage || 'Failed start', ErrorSeverity.MEDIUM, 'StartSim'); }
          return { success: r.success, status: r.status, error: r.errorMessage };
      } catch (error: any) {
          // Handle exceptions during API call
          if (this.isDisposed) return { success: false, error: 'Disposed' }; const e=error instanceof Error ? error.message : String(error); this.logger.error('Error starting sim', { error: e }); appState.updateConnectionState({ simulatorStatus: 'ERROR', lastConnectionError: e }); this.desiredState.simulatorRunning = false; AppErrorHandler.handleGenericError(e, ErrorSeverity.HIGH, 'StartSimEx'); return { success: false, error: e };
      }
  }

  /** Stops the simulator after checking connection status. */
   public async stopSimulator(): Promise<SimulatorActionResult> {
       if (this.isDisposed) return { success: false, error: 'CM disposed' };
       this.desiredState.simulatorRunning = false; // Set intent
       const state = appState.getState().connection;
       if (state.webSocketStatus !== ConnectionStatus.CONNECTED) { const e = 'Stop sim fail: Not connected'; return { success: false, error: e }; }
       // Prevent stopping if already stopped/stopping or not running/starting
       if (state.simulatorStatus !== 'RUNNING' && state.simulatorStatus !== 'STARTING') { this.logger.warn(`Stop sim ignored: Status=${state.simulatorStatus}`); return { success: true, status: state.simulatorStatus }; }

       this.logger.info('Stopping simulator...');
       appState.updateConnectionState({ simulatorStatus: 'STOPPING' }); // Optimistic UI update
       try {
           const r: SimulatorStatusResponse = await this.simulatorManager.stopSimulator(); // Call API
           if (this.isDisposed) return { success: false, error: 'Disposed' };
           // Update state based on API response
           const status = r.success ? 'STOPPED' : 'ERROR';
           const errorMsg = r.success ? null : (r.errorMessage || 'Failed stop');
           appState.updateConnectionState({ simulatorStatus: status, lastConnectionError: errorMsg });
           if (!r.success) { AppErrorHandler.handleGenericError(errorMsg || 'Failed stop', ErrorSeverity.MEDIUM, 'StopSim'); }
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
}