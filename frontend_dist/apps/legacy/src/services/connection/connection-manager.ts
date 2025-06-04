// src/services/connection/connection-manager.ts
import { getLogger } from '../../boot/logging';

import { config } from '../../config';

import { TokenManager } from '../auth/token-manager';
import { DeviceIdManager } from '../auth/device-id-manager';
import { toastService } from '../notification/toast-service';

import { Resilience, ResilienceState } from './resilience';
import { SimulatorClient } from './simulator-client';
import { SocketClient } from './socket-client';
import { Heartbeat } from './heartbeat';

import { SessionHandler } from '../websocket/message-handlers/session';

import { connectionState, ConnectionStatus } from '../../state/connection-state';
import { authState } from '../../state/auth-state';

import { handleError } from '../../utils/error-handling';
import { Disposable } from '@shared/services';
import { EventEmitter } from '@shared/services';

export interface ConnectionManagerOptions {
  heartbeatInterval?: number;
  heartbeatTimeout?: number;
  resilience?: {
    initialDelayMs?: number;
    maxDelayMs?: number;
    maxAttempts?: number;
    suspensionTimeoutMs?: number;
    failureThreshold?: number;
    jitterFactor?: number;
  };
}

export interface ConnectionDesiredState {
  connected: boolean;
  simulatorRunning: boolean;
}

export class ConnectionManager implements Disposable {
  private logger = getLogger('ConnectionManager');
  private socketClient: SocketClient;
  private heartbeat: Heartbeat;
  private resilience: Resilience;
  private sessionHandler: SessionHandler;
  private simulatorClient: SimulatorClient;
  private isDisposed = false;
  
  public desiredState: ConnectionDesiredState = {
    connected: false,
    simulatorRunning: false
  };
  
  private events = new EventEmitter<{
    auth_failed: { reason: string };
    device_id_changed: { oldDeviceId: string; newDeviceId: string };
    device_id_invalidated: { deviceId: string; reason?: string };
  }>();

  constructor(
    tokenManager: TokenManager,
    options: ConnectionManagerOptions = {}
  ) {
    this.logger.info('Initializing ConnectionManager');
    
    // Use config for reconnection defaults, with option to override
    const reconnectionConfig = config.reconnection;
    const mergedOptions: ConnectionManagerOptions = {
        heartbeatInterval: options.heartbeatInterval || 15000,
        heartbeatTimeout: options.heartbeatTimeout || 5000,
        resilience: {
            initialDelayMs: options.resilience?.initialDelayMs || reconnectionConfig.initialDelayMs,
            maxDelayMs: options.resilience?.maxDelayMs || reconnectionConfig.maxDelayMs,
            maxAttempts: options.resilience?.maxAttempts || reconnectionConfig.maxAttempts,
            jitterFactor: options.resilience?.jitterFactor || reconnectionConfig.jitterFactor,
            suspensionTimeoutMs: options.resilience?.suspensionTimeoutMs || 60000, // Default if not provided
        }
    };

    // Initialize socket client
    this.socketClient = new SocketClient(tokenManager);
    
    // Initialize handlers
    this.heartbeat = new Heartbeat(this.socketClient, {
      interval: options.heartbeatInterval || 15000,
      timeout: options.heartbeatTimeout || 5000
    });
    
    this.resilience = new Resilience(tokenManager, options.resilience);
    this.sessionHandler = new SessionHandler(this.socketClient);
    this.simulatorClient = new SimulatorClient(this.socketClient);
    
    // Setup event listeners
    this.setupListeners();
  }

  private setupListeners(): void {
    // Listen for socket client status changes
    this.socketClient.getStatus().subscribe(status => {
        if (this.isDisposed) return;
        
        // Update connection state
        connectionState.updateState({
            webSocketStatus: status
        });
        
        // Handle status changes
        if (status === ConnectionStatus.CONNECTED) {
            this.logger.info('WebSocket connected. Not starting heartbeat automatically.');
            
            // DO NOT start heartbeat here - we'll start it after session validation
            
            this.resilience.reset();
            this.syncSimulatorState();
        } else if (status === ConnectionStatus.DISCONNECTED) {
            this.logger.info('WebSocket disconnected. Stopping heartbeat.');
            this.heartbeat.stop();
            
            // Attempt recovery if needed
            if (this.desiredState.connected && authState.getState().isAuthenticated) {
                this.attemptRecovery('ws_disconnect');
            }
        }
    });
    
    // Listen for auth state changes
    authState.select(state => state.isAuthenticated).subscribe(isAuthenticated => {
      if (this.isDisposed) return;
      
      this.logger.info(`Auth state changed: isAuthenticated=${isAuthenticated}`);
      this.resilience.updateAuthState(isAuthenticated);
      
      if (isAuthenticated) {
        // Set desired state and trigger connection if needed
        this.setDesiredState({ connected: true });
      } else {
        // Ensure disconnect if not authenticated
        this.setDesiredState({ connected: false });
      }
    });
    
    // Listen for heartbeat events
    this.heartbeat.on('timeout', () => {
      if (this.isDisposed) return;
      
      this.logger.warn('Heartbeat timeout detected. Disconnecting WebSocket.');
      this.socketClient.disconnect('heartbeat_timeout');
    });
    
    this.heartbeat.on('response', (data) => {
      if (this.isDisposed) return;
      
      // Check device ID validity
      if (!data.deviceIdValid) {
        this.logger.warn('Device ID invalidated by heartbeat response');
        this.handleDeviceIdInvalidation('heartbeat_response');
      }
    });
    
    // Listen for WebSocket messages
    this.socketClient.on('message', (message) => {
      if (this.isDisposed) return;
      
      // Handle device ID invalidation
      if ((message as any).type === 'device_id_invalidated') {
        this.logger.warn(`Device ID invalidated: ${(message as any).deviceId}`);
        this.handleDeviceIdInvalidation('server_message', (message as any).reason);
      }
    });
  }

  // Add a reset method that fully resets the connection state
  public resetState(): void {
    if (this.isDisposed) return;
    
    this.logger.info('Resetting connection manager state');
    
    // Force disconnect if connected
    this.disconnect('reset');
    
    // Reset desired state
    this.desiredState = {
      connected: false,
      simulatorRunning: false
    };
    
    // Reset resilience
    this.resilience.reset();
    
    // Update connection state
    connectionState.updateState({
      webSocketStatus: ConnectionStatus.DISCONNECTED,
      overallStatus: ConnectionStatus.DISCONNECTED,
      isRecovering: false,
      recoveryAttempt: 0,
      simulatorStatus: 'UNKNOWN',
      lastConnectionError: null
    });
  }

  /**
   * Updates the desired state and triggers synchronization.
   */
  public setDesiredState(state: Partial<ConnectionDesiredState>): void {
    if (this.isDisposed) {
      this.logger.warn('Cannot set desired state: ConnectionManager is disposed');
      return;
    }
    
    const oldState = { ...this.desiredState };
    this.desiredState = { ...this.desiredState, ...state };
    
    this.logger.info('Desired state updated', {
      oldState,
      newState: this.desiredState
    });
    
    // Trigger state sync
    this.syncConnectionState();
    
    // Sync simulator if needed
    if (oldState.simulatorRunning !== this.desiredState.simulatorRunning) {
      this.syncSimulatorState();
    }
  }

  /**
   * Synchronizes the actual connection state with the desired state.
   */
  private syncConnectionState(): void {
    if (this.isDisposed) return;
    
    const wsStatus = connectionState.getState().webSocketStatus;
    const isRecovering = connectionState.getState().isRecovering;
    const authIsAuthenticated = authState.getState().isAuthenticated;
    const resilienceState = this.resilience.getState().state;
    
    // Skip if auth still loading
    if (authState.getState().isAuthLoading) {
      this.logger.debug('Sync connection state skipped: Auth loading');
      return;
    }
    
    // Skip if not authenticated
    if (!authIsAuthenticated) {
      this.logger.debug('Sync connection state skipped: Not authenticated');
      return;
    }
    
    // Skip if resilience prevents connections
    if (resilienceState === ResilienceState.SUSPENDED || resilienceState === ResilienceState.FAILED) {
      this.logger.debug(`Sync connection state skipped: Resilience state is ${resilienceState}`);
      return;
    }
    
    // Condition to connect
    if (this.desiredState.connected && 
        wsStatus !== ConnectionStatus.CONNECTED && 
        wsStatus !== ConnectionStatus.CONNECTING && 
        !isRecovering) {
      this.logger.info('Sync connection state: Initiating connection');
      this.connect().catch(err => {
        this.logger.error('Connect promise rejected', {
          error: err instanceof Error ? err.message : String(err)
        });
      });
    }
    // Condition to disconnect
    else if (!this.desiredState.connected && 
             (wsStatus === ConnectionStatus.CONNECTED || 
              wsStatus === ConnectionStatus.CONNECTING || 
              isRecovering)) {
      this.logger.info('Sync connection state: Disconnecting');
      this.disconnect('desired_state_sync');
    }
    // No action needed
    else {
      this.logger.debug('Sync connection state: No action needed');
    }
  }

  /**
   * Synchronizes the simulator state with the desired state.
   */
  private async syncSimulatorState(): Promise<void> {
    if (this.isDisposed) return;
    
    const wsStatus = connectionState.getState().webSocketStatus;
    
    if (wsStatus !== ConnectionStatus.CONNECTED) {
      this.logger.debug('Sync simulator state skipped: Not connected');
      return;
    }
    
    const simStatus = connectionState.getState().simulatorStatus;
    const isRunning = simStatus === 'RUNNING';
    const isBusy = simStatus === 'STARTING' || simStatus === 'STOPPING';
    
    if (this.desiredState.simulatorRunning && !isRunning && !isBusy) {
      this.logger.info('Syncing simulator state: Starting simulator');
      await this.startSimulator();
    }
    else if (!this.desiredState.simulatorRunning && isRunning && !isBusy) {
      this.logger.info('Syncing simulator state: Stopping simulator');
      await this.stopSimulator();
    }
    else {
      this.logger.debug('Sync simulator state: No action needed');
    }
  }

  /**
   * Establishes the WebSocket connection and validates the session.
   */
  public async connect(): Promise<boolean> {
    if (this.isDisposed) return false;
    
    // Check authentication
    if (!authState.getState().isAuthenticated) {
        this.logger.error('Connect failed: Not authenticated');
        return false;
    }
    
    // Check if already connected/connecting/recovering
    const connState = connectionState.getState();
    if (connState.webSocketStatus === ConnectionStatus.CONNECTED || 
        connState.webSocketStatus === ConnectionStatus.CONNECTING || 
        connState.isRecovering) {
        this.logger.warn(`Connect ignored: Status=${connState.webSocketStatus}, Recovering=${connState.isRecovering}`);
        return connState.webSocketStatus === ConnectionStatus.CONNECTED;
    }
    
    this.logger.info('Initiating connection process');
    
    // Update state to connecting
    connectionState.updateState({
        webSocketStatus: ConnectionStatus.CONNECTING,
        lastConnectionError: null
    });
    
    try {
        // 1. Connect WebSocket
        const wsConnected = await this.socketClient.connect();
        
        if (!wsConnected) {
            throw new Error('WebSocket connection failed');
        }
        
        this.logger.info('WebSocket connected, now requesting session info');
        
        // 2. Request session info first and wait for response
        let sessionResponse;
        try {
            // Important: Wait for this response before proceeding
            sessionResponse = await this.sessionHandler.requestSessionInfo();
            
            this.logger.info('Session info response received', { 
                success: sessionResponse.success,
                type: sessionResponse.type,
                deviceId: sessionResponse.deviceId,
                expiresAt: sessionResponse.expiresAt,
                simulatorStatus: sessionResponse.simulatorStatus
            });
            
            // Determine success based on response contents, not just success flag
            const sessionSuccess = sessionResponse.type === 'session_info' && sessionResponse.deviceId;
            
            if (!sessionSuccess) {
                throw new Error(`Session validation failed: ${sessionResponse.error || 'Unknown error'}`);
            }
        } catch (sessionError) {
            this.logger.error('Session request failed', { 
                error: sessionError instanceof Error ? sessionError.message : String(sessionError)
            });
            throw sessionError; // Propagate error
        }
        
        // Update connection state to CONNECTED since session is validated
        connectionState.updateState({
            webSocketStatus: ConnectionStatus.CONNECTED,
            overallStatus: ConnectionStatus.CONNECTED,
            simulatorStatus: sessionResponse.simulatorStatus || 'NONE'
        });
        
        // Log immediately after to verify the update happened
        const updatedState = connectionState.getState();
        this.logger.info('Connection state after explicit update', {
            webSocketStatus: updatedState.webSocketStatus,
            overallStatus: updatedState.overallStatus,
            isConnected: updatedState.overallStatus === ConnectionStatus.CONNECTED,
        });

        // 3. Only start sending heartbeats AFTER successful session response
        this.logger.info('Session validated successfully, starting heartbeats');
        this.heartbeat.start();
        
        // Log current state for debugging
        this.logConnectionState();
        
        return true;
    } catch (error: any) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        this.logger.error(`Connection process failed: ${errorMessage}`);
        
        // Update connection state
        connectionState.updateState({
            webSocketStatus: ConnectionStatus.DISCONNECTED,
            lastConnectionError: errorMessage
        });
        
        // Record failure and attempt recovery
        this.resilience.recordFailure(`Connection process error: ${errorMessage}`);
        this.attemptRecovery('connect_error');
        
        return handleError(
            errorMessage,
            'ConnectionProcess',
            'high'
        ).success;
    }
  }


  /**
   * Disconnects the WebSocket and cleans up resources.
   */
  public async disconnect(reason: string = 'manual'): Promise<boolean> {
    if (this.isDisposed && reason !== 'dispose') return true;
    
    this.logger.info(`Disconnecting. Reason: ${reason}`);
    
    const wsStatus = connectionState.getState().webSocketStatus;
    if (wsStatus === ConnectionStatus.DISCONNECTED && !connectionState.getState().isRecovering) {
      this.logger.debug('Disconnect ignored: Already disconnected');
      return true;
    }
    
    try {
      // Stop session if connected
      if (wsStatus === ConnectionStatus.CONNECTED) {
        this.logger.info('Stopping session before disconnecting');
        try {
          const response = await this.sessionHandler.stopSession();
          
          if (response.success) {
            this.logger.info('Session stop request successful');
            connectionState.updateState({ simulatorStatus: 'STOPPED' });
            this.desiredState.simulatorRunning = false;
          } else {
            this.logger.warn(`Session stop request failed: ${response.error}`);
          }
        } catch (error: any) {
          this.logger.error('Error stopping session', {
            error: error instanceof Error ? error.message : String(error)
          });
        }
      }
      
      // Reset resilience and stop heartbeat
      this.resilience.reset();
      this.heartbeat.stop();
      
      // Disconnect socket
      this.socketClient.disconnect(reason);
      
      // Update connection state
      connectionState.updateState({
        webSocketStatus: ConnectionStatus.DISCONNECTED,
        isRecovering: false,
        recoveryAttempt: 0,
        lastConnectionError: `Disconnected: ${reason}`
      });
      
      return true;
    } catch (error: any) {
      this.logger.error(`Error during disconnect: ${error instanceof Error ? error.message : String(error)}`);
      return false;
    }
  }

  /**
   * Attempts to recover a lost connection.
   */
  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    if (this.isDisposed) return false;
    
    // Check auth state
    if (!authState.getState().isAuthenticated) {
        this.logger.warn('Recovery ignored: Not authenticated');
        return false;
    }
    
    // Check if already recovering or resilience prevents recovery
    const connState = connectionState.getState();
    const resilienceState = this.resilience.getState();
    
    if (connState.isRecovering || 
        resilienceState.state === ResilienceState.SUSPENDED || 
        resilienceState.state === ResilienceState.FAILED) {
        this.logger.warn(`Recovery ignored: Already recovering or resilience prevents (${resilienceState.state})`);
        return false;
    }
    
    this.logger.info(`Attempting recovery. Reason: ${reason}`);
    
    // Update state to show recovery starting
    connectionState.updateState({
        isRecovering: true,
        recoveryAttempt: resilienceState.attempt + 1
    });
    
    // Register a one-time listener for reconnection success
    const successSubscription = this.resilience.on('reconnect_success', async (data) => {
        // Cleanup the listener to avoid memory leaks
        successSubscription.unsubscribe();
        
        try {
            // Request session info after a successful reconnect
            this.logger.info('Reconnection successful, requesting session info');
            const sessionResponse = await this.sessionHandler.requestSessionInfo();
            
            if (sessionResponse.type === 'session_info' && sessionResponse.deviceId) {
                this.logger.info('Session validated after reconnect, starting heartbeats');
                
                // Update connection state to CONNECTED
                connectionState.updateState({
                    webSocketStatus: ConnectionStatus.CONNECTED,
                    overallStatus: ConnectionStatus.CONNECTED,
                    simulatorStatus: sessionResponse.simulatorStatus || 'NONE',
                    isRecovering: false,
                    recoveryAttempt: 0
                });
                
                // Start heartbeats
                this.heartbeat.start();
                
                // Log current state for debugging
                this.logConnectionState();
            } else {
                this.logger.error('Session validation failed after reconnect');
                // Handle session validation failure
                this.disconnect('session_validation_failed');
            }
        } catch (error: any) {
            this.logger.error('Error validating session after reconnect', {
                error: error instanceof Error ? error.message : String(error)
            });
            // Handle error
            this.disconnect('session_validation_error');
        }
    });
    
    // Register a one-time listener for reconnection failure
    const failureSubscription = this.resilience.on('reconnect_failure', () => {
        // Cleanup the listener to avoid memory leaks
        failureSubscription.unsubscribe();
        
        // Don't need to do anything special here as resilience will handle 
        // further reconnection attempts if appropriate
        this.logger.warn('Reconnection attempt failed');
    });
    
    // Attempt reconnection via resilience manager
    const initiated = await this.resilience.attemptReconnection(() => this.connect());
    
    if (!initiated) {
        this.logger.warn('Recovery could not be initiated');
        connectionState.updateState({
            isRecovering: false,
            recoveryAttempt: 0
        });
        
        // Cleanup listeners if we couldn't even initiate recovery
        successSubscription.unsubscribe();
        failureSubscription.unsubscribe();
    } else {
        this.logger.info('Recovery process initiated');
    }
    
    return initiated;
  }

  // Add this helper method for state debugging
  private logConnectionState(): void {
    const state = connectionState.getState();
    this.logger.info('Current connection state', {
        overallStatus: state.overallStatus,
        webSocketStatus: state.webSocketStatus,
        isConnected: state.overallStatus === ConnectionStatus.CONNECTED,
        isConnecting: state.overallStatus === ConnectionStatus.CONNECTING,
        isRecovering: state.isRecovering,
        simulatorStatus: state.simulatorStatus,
        heartbeatActive: this.heartbeat.isActive() // Call the method instead of accessing the property
    });
  }

  /**
   * Manually initiates a reconnection.
   */
  public async manualReconnect(): Promise<boolean> {
    this.logger.info('Manual reconnect triggered');
    
    if (this.isDisposed) return false;
    
    // Set desire to connect
    this.setDesiredState({ connected: true });
    
    // Use socket reconnect if connected, otherwise attempt recovery
    const wsStatus = connectionState.getState().webSocketStatus;
      
    // Show reconnection attempt toast to user - with a stable ID
    toastService.info('Attempting to reconnect...', 5000, 'connection-recovery-attempt');
    
    if (wsStatus === ConnectionStatus.CONNECTED) {
      this.socketClient.disconnect('manual_reconnect');
      return this.attemptRecovery('manual_user_request');
    } else {
      return this.attemptRecovery('manual_user_request');
    }
  }

  /**
   * Handles device ID invalidation.
   */
  private handleDeviceIdInvalidation(source: string, reason?: string): void {
    if (this.isDisposed) return;
    
    this.logger.warn(`Device ID invalidated. Source: ${source}, Reason: ${reason || 'Unknown'}`);
    
    // Clear device ID
    const deviceId = DeviceIdManager.getInstance().getDeviceId();
    DeviceIdManager.getInstance().clearDeviceId();
    
    // Show toast notification to user about the session issue
    toastService.error(`Your session has been deactivated: ${reason || 'Device ID invalidated'}`, 0);
    
    // Emit event
    this.events.emit('device_id_invalidated', {
      deviceId,
      reason
    });
    
    // Disconnect
    this.disconnect('device_id_invalidated');
    
    // Update auth state
    authState.updateState({
      lastAuthError: `Device ID invalidated: ${reason || 'Unknown reason'}`
    });
  }

  /**
   * Starts the simulator.
   */
  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    if (this.isDisposed) {
      return { success: false, error: 'ConnectionManager disposed' };
    }
    
    // Set desired state
    this.desiredState.simulatorRunning = true;
    
    // Check connection status
    const connState = connectionState.getState();
    
    if (connState.webSocketStatus !== ConnectionStatus.CONNECTED) {
      return { success: false, error: 'Not connected' };
    }
    
    // Prevent starting if already running/starting
    if (connState.simulatorStatus === 'RUNNING' || connState.simulatorStatus === 'STARTING') {
      this.logger.warn(`Start simulator ignored: Status=${connState.simulatorStatus}`);
      return { success: true, status: connState.simulatorStatus };
    }
    
    // Start simulator
    return this.simulatorClient.startSimulator();
  }

  /**
   * Stops the simulator.
   */
  public async stopSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    if (this.isDisposed) {
      return { success: false, error: 'ConnectionManager disposed' };
    }
    
    // Set desired state
    this.desiredState.simulatorRunning = false;
    
    // Check connection status
    const connState = connectionState.getState();
    
    if (connState.webSocketStatus !== ConnectionStatus.CONNECTED) {
      return { success: false, error: 'Not connected' };
    }
    
    // Prevent stopping if not running/starting
    if (connState.simulatorStatus !== 'RUNNING' && connState.simulatorStatus !== 'STARTING') {
      this.logger.warn(`Stop simulator ignored: Status=${connState.simulatorStatus}`);
      return { success: true, status: connState.simulatorStatus };
    }
    
    // Stop simulator
    return this.simulatorClient.stopSimulator();
  }

  /**
   * Subscribe to events.
   */
  public on<T extends keyof typeof this.events.events>(
    event: T,
    callback: (data: typeof this.events.events[T]) => void
  ): { unsubscribe: () => void } {
    return this.events.on(event, callback);
  }

  /**
   * Disposes of resources.
   */
  public dispose(): void {
    if (this.isDisposed) return;
    this.isDisposed = true;
    
    this.logger.info('Disposing ConnectionManager');
    
    // Disconnect WebSocket
    this.disconnect('dispose');
    
    // Dispose of managed resources
    this.heartbeat.dispose();
    this.resilience.dispose();
    
    // Clean up events
    this.events.clear();
    
    this.logger.info('ConnectionManager disposed');
  }

  [Symbol.dispose](): void {
    this.dispose();
  }
}