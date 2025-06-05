// src/client/connection-manager.ts
import { getLogger } from '@trading-app/logging';
import { TokenManager, DeviceIdManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { Disposable, EventEmitter, handleError } from '@trading-app/utils';

import { SocketClient } from './socket-client';
import { SessionHandler } from '../handlers/session-handler';
import { SimulatorHandler } from '../handlers/simulator-handler';
import { Heartbeat } from '../services/heartbeat';
import { Resilience, ResilienceState } from '../services/resilience';
import { SimulatorClient } from '../services/simulator-client';

import { 
  ConnectionDesiredState, 
  ConnectionManagerOptions,
  ToastService,
  StateManager,
  ConfigService
} from '../types/connection-types';

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
    private tokenManager: TokenManager,
    private stateManager: StateManager,
    private toastService: ToastService,
    private configService: ConfigService,
    options: ConnectionManagerOptions = {}
  ) {
    this.logger.info('Initializing ConnectionManager');
    
    const reconnectionConfig = this.configService.getReconnectionConfig();
    const mergedOptions: ConnectionManagerOptions = {
      heartbeatInterval: options.heartbeatInterval || 15000,
      heartbeatTimeout: options.heartbeatTimeout || 5000,
      resilience: {
        initialDelayMs: options.resilience?.initialDelayMs || reconnectionConfig.initialDelayMs,
        maxDelayMs: options.resilience?.maxDelayMs || reconnectionConfig.maxDelayMs,
        maxAttempts: options.resilience?.maxAttempts || reconnectionConfig.maxAttempts,
        jitterFactor: options.resilience?.jitterFactor || reconnectionConfig.jitterFactor,
        suspensionTimeoutMs: options.resilience?.suspensionTimeoutMs || 60000,
      }
    };

    // Initialize socket client
    this.socketClient = new SocketClient(tokenManager, configService);
    
    // Initialize handlers
    this.heartbeat = new Heartbeat(this.socketClient, this.stateManager, {
      interval: options.heartbeatInterval || 15000,
      timeout: options.heartbeatTimeout || 5000
    });
    
    this.resilience = new Resilience(tokenManager, toastService, options.resilience);
    this.sessionHandler = new SessionHandler(this.socketClient);
    this.simulatorClient = new SimulatorClient(this.socketClient, this.stateManager);
    
    // Setup event listeners
    this.setupListeners();
  }

  private setupListeners(): void {
    // Listen for socket client status changes
    this.socketClient.getStatus().subscribe(status => {
      if (this.isDisposed) return;
      
      this.stateManager.updateConnectionState({
        webSocketStatus: status
      });
      
      if (status === ConnectionStatus.CONNECTED) {
        this.logger.info('WebSocket connected. Not starting heartbeat automatically.');
        this.resilience.reset();
        this.syncSimulatorState();
      } else if (status === ConnectionStatus.DISCONNECTED) {
        this.logger.info('WebSocket disconnected. Stopping heartbeat.');
        this.heartbeat.stop();
        
        if (this.desiredState.connected && this.stateManager.getAuthState().isAuthenticated) {
          this.attemptRecovery('ws_disconnect');
        }
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
      
      if (!data.deviceIdValid) {
        this.logger.warn('Device ID invalidated by heartbeat response');
        this.handleDeviceIdInvalidation('heartbeat_response');
      }
    });
    
    // Listen for WebSocket messages
    this.socketClient.on('message', (message) => {
      if (this.isDisposed) return;
      
      if ((message as any).type === 'device_id_invalidated') {
        this.logger.warn(`Device ID invalidated: ${(message as any).deviceId}`);
        this.handleDeviceIdInvalidation('server_message', (message as any).reason);
      }
    });
  }

  public resetState(): void {
    if (this.isDisposed) return;
    
    this.logger.info('Resetting connection manager state');
    
    this.disconnect('reset');
    
    this.desiredState = {
      connected: false,
      simulatorRunning: false
    };
    
    this.resilience.reset();
    
    this.stateManager.updateConnectionState({
      webSocketStatus: ConnectionStatus.DISCONNECTED,
      overallStatus: ConnectionStatus.DISCONNECTED,
      isRecovering: false,
      recoveryAttempt: 0,
      simulatorStatus: 'UNKNOWN',
      lastConnectionError: null
    });
  }

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
    
    this.syncConnectionState();
    
    if (oldState.simulatorRunning !== this.desiredState.simulatorRunning) {
      this.syncSimulatorState();
    }
  }

  private syncConnectionState(): void {
    if (this.isDisposed) return;
    
    const connState = this.stateManager.getConnectionState();
    const authState = this.stateManager.getAuthState();
    const resilienceState = this.resilience.getState().state;
    
    if (authState.isAuthLoading) {
      this.logger.debug('Sync connection state skipped: Auth loading');
      return;
    }
    
    if (!authState.isAuthenticated) {
      this.logger.debug('Sync connection state skipped: Not authenticated');
      return;
    }
    
    if (resilienceState === ResilienceState.SUSPENDED || resilienceState === ResilienceState.FAILED) {
      this.logger.debug(`Sync connection state skipped: Resilience state is ${resilienceState}`);
      return;
    }
    
    if (this.desiredState.connected && 
        connState.webSocketStatus !== ConnectionStatus.CONNECTED && 
        connState.webSocketStatus !== ConnectionStatus.CONNECTING && 
        !connState.isRecovering) {
      this.logger.info('Sync connection state: Initiating connection');
      this.connect().catch(err => {
        this.logger.error('Connect promise rejected', {
          error: err instanceof Error ? err.message : String(err)
        });
      });
    }
    else if (!this.desiredState.connected && 
             (connState.webSocketStatus === ConnectionStatus.CONNECTED || 
              connState.webSocketStatus === ConnectionStatus.CONNECTING || 
              connState.isRecovering)) {
      this.logger.info('Sync connection state: Disconnecting');
      this.disconnect('desired_state_sync');
    }
  }

  private async syncSimulatorState(): Promise<void> {
    if (this.isDisposed) return;
    
    const connState = this.stateManager.getConnectionState();
    
    if (connState.webSocketStatus !== ConnectionStatus.CONNECTED) {
      this.logger.debug('Sync simulator state skipped: Not connected');
      return;
    }
    
    const simStatus = connState.simulatorStatus;
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
  }

  public async connect(): Promise<boolean> {
    if (this.isDisposed) return false;
    
    const authState = this.stateManager.getAuthState();
    if (!authState.isAuthenticated) {
      this.logger.error('Connect failed: Not authenticated');
      return false;
    }
    
    const connState = this.stateManager.getConnectionState();
    if (connState.webSocketStatus === ConnectionStatus.CONNECTED || 
        connState.webSocketStatus === ConnectionStatus.CONNECTING || 
        connState.isRecovering) {
      this.logger.warn(`Connect ignored: Status=${connState.webSocketStatus}, Recovering=${connState.isRecovering}`);
      return connState.webSocketStatus === ConnectionStatus.CONNECTED;
    }
    
    this.logger.info('Initiating connection process');
    
    this.stateManager.updateConnectionState({
      webSocketStatus: ConnectionStatus.CONNECTING,
      lastConnectionError: null
    });
    
    try {
      const wsConnected = await this.socketClient.connect();
      
      if (!wsConnected) {
        throw new Error('WebSocket connection failed');
      }
      
      this.logger.info('WebSocket connected, now requesting session info');
      
      let sessionResponse;
      try {
        sessionResponse = await this.sessionHandler.requestSessionInfo();
        
        this.logger.info('Session info response received', { 
          success: sessionResponse.success,
          type: sessionResponse.type,
          deviceId: sessionResponse.deviceId,
          expiresAt: sessionResponse.expiresAt,
          simulatorStatus: sessionResponse.simulatorStatus
        });
        
        const sessionSuccess = sessionResponse.type === 'session_info' && sessionResponse.deviceId;
        
        if (!sessionSuccess) {
          throw new Error(`Session validation failed: ${sessionResponse.error || 'Unknown error'}`);
        }
      } catch (sessionError) {
        this.logger.error('Session request failed', { 
          error: sessionError instanceof Error ? sessionError.message : String(sessionError)
        });
        throw sessionError;
      }
      
      this.stateManager.updateConnectionState({
        webSocketStatus: ConnectionStatus.CONNECTED,
        overallStatus: ConnectionStatus.CONNECTED,
        simulatorStatus: sessionResponse.simulatorStatus || 'NONE'
      });
      
      this.logger.info('Session validated successfully, starting heartbeats');
      this.heartbeat.start();
      
      return true;
    } catch (error: any) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      this.logger.error(`Connection process failed: ${errorMessage}`);
      
      this.stateManager.updateConnectionState({
        webSocketStatus: ConnectionStatus.DISCONNECTED,
        lastConnectionError: errorMessage
      });
      
      this.resilience.recordFailure(`Connection process error: ${errorMessage}`);
      this.attemptRecovery('connect_error');
      
      return handleError(
        errorMessage,
        'ConnectionProcess',
        'high'
      ).success;
    }
  }

  public async disconnect(reason: string = 'manual'): Promise<boolean> {
    if (this.isDisposed && reason !== 'dispose') return true;
    
    this.logger.info(`Disconnecting. Reason: ${reason}`);
    
    const connState = this.stateManager.getConnectionState();
    if (connState.webSocketStatus === ConnectionStatus.DISCONNECTED && !connState.isRecovering) {
      this.logger.debug('Disconnect ignored: Already disconnected');
      return true;
    }
    
    try {
      if (connState.webSocketStatus === ConnectionStatus.CONNECTED) {
        this.logger.info('Stopping session before disconnecting');
        try {
          const response = await this.sessionHandler.stopSession();
          
          if (response.success) {
            this.logger.info('Session stop request successful');
            this.stateManager.updateConnectionState({ simulatorStatus: 'STOPPED' });
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
      
      this.resilience.reset();
      this.heartbeat.stop();
      
      this.socketClient.disconnect(reason);
      
      this.stateManager.updateConnectionState({
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

  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    if (this.isDisposed) return false;
    
    const authState = this.stateManager.getAuthState();
    if (!authState.isAuthenticated) {
      this.logger.warn('Recovery ignored: Not authenticated');
      return false;
    }
    
    const connState = this.stateManager.getConnectionState();
    const resilienceState = this.resilience.getState();
    
    if (connState.isRecovering || 
        resilienceState.state === ResilienceState.SUSPENDED || 
        resilienceState.state === ResilienceState.FAILED) {
      this.logger.warn(`Recovery ignored: Already recovering or resilience prevents (${resilienceState.state})`);
      return false;
    }
    
    this.logger.info(`Attempting recovery. Reason: ${reason}`);
    
    this.stateManager.updateConnectionState({
      isRecovering: true,
      recoveryAttempt: resilienceState.attempt + 1
    });
    
    const successSubscription = this.resilience.on('reconnect_success', async (data) => {
      successSubscription.unsubscribe();
      
      try {
        this.logger.info('Reconnection successful, requesting session info');
        const sessionResponse = await this.sessionHandler.requestSessionInfo();
        
        if (sessionResponse.type === 'session_info' && sessionResponse.deviceId) {
          this.logger.info('Session validated after reconnect, starting heartbeats');
          
          this.stateManager.updateConnectionState({
            webSocketStatus: ConnectionStatus.CONNECTED,
            overallStatus: ConnectionStatus.CONNECTED,
            simulatorStatus: sessionResponse.simulatorStatus || 'NONE',
            isRecovering: false,
            recoveryAttempt: 0
          });
          
          this.heartbeat.start();
        } else {
          this.logger.error('Session validation failed after reconnect');
          this.disconnect('session_validation_failed');
        }
      } catch (error: any) {
        this.logger.error('Error validating session after reconnect', {
          error: error instanceof Error ? error.message : String(error)
        });
        this.disconnect('session_validation_error');
      }
    });
    
    const failureSubscription = this.resilience.on('reconnect_failure', () => {
      failureSubscription.unsubscribe();
      this.logger.warn('Reconnection attempt failed');
    });
    
    const initiated = await this.resilience.attemptReconnection(() => this.connect());
    
    if (!initiated) {
      this.logger.warn('Recovery could not be initiated');
      this.stateManager.updateConnectionState({
        isRecovering: false,
        recoveryAttempt: 0
      });
      
      successSubscription.unsubscribe();
      failureSubscription.unsubscribe();
    } else {
      this.logger.info('Recovery process initiated');
    }
    
    return initiated;
  }

  public async manualReconnect(): Promise<boolean> {
    this.logger.info('Manual reconnect triggered');
    
    if (this.isDisposed) return false;
    
    this.setDesiredState({ connected: true });
    
    const connState = this.stateManager.getConnectionState();
    
    this.toastService.info('Attempting to reconnect...', 5000, 'connection-recovery-attempt');
    
    if (connState.webSocketStatus === ConnectionStatus.CONNECTED) {
      this.socketClient.disconnect('manual_reconnect');
      return this.attemptRecovery('manual_user_request');
    } else {
      return this.attemptRecovery('manual_user_request');
    }
  }

  private handleDeviceIdInvalidation(source: string, reason?: string): void {
    if (this.isDisposed) return;
    
    this.logger.warn(`Device ID invalidated. Source: ${source}, Reason: ${reason || 'Unknown'}`);
    
    const deviceId = DeviceIdManager.getInstance().getDeviceId();
    DeviceIdManager.getInstance().clearDeviceId();
    
    this.toastService.error(`Your session has been deactivated: ${reason || 'Device ID invalidated'}`, 0);
    
    this.events.emit('device_id_invalidated', {
      deviceId,
      reason
    });
    
    this.disconnect('device_id_invalidated');
  }

  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    if (this.isDisposed) {
      return { success: false, error: 'ConnectionManager disposed' };
    }
    
    this.desiredState.simulatorRunning = true;
    
    const connState = this.stateManager.getConnectionState();
    
    if (connState.webSocketStatus !== ConnectionStatus.CONNECTED) {
      return { success: false, error: 'Not connected' };
    }
    
    if (connState.simulatorStatus === 'RUNNING' || connState.simulatorStatus === 'STARTING') {
      this.logger.warn(`Start simulator ignored: Status=${connState.simulatorStatus}`);
      return { success: true, status: connState.simulatorStatus };
    }
    
    return this.simulatorClient.startSimulator();
  }

  public async stopSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    if (this.isDisposed) {
      return { success: false, error: 'ConnectionManager disposed' };
    }
    
    this.desiredState.simulatorRunning = false;
    
    const connState = this.stateManager.getConnectionState();
    
    if (connState.webSocketStatus !== ConnectionStatus.CONNECTED) {
      return { success: false, error: 'Not connected' };
    }
    
    if (connState.simulatorStatus !== 'RUNNING' && connState.simulatorStatus !== 'STARTING') {
      this.logger.warn(`Stop simulator ignored: Status=${connState.simulatorStatus}`);
      return { success: true, status: connState.simulatorStatus };
    }
    
    return this.simulatorClient.stopSimulator();
  }

  public on<T extends keyof typeof this.events.events>(
    event: T,
    callback: (data: typeof this.events.events[T]) => void
  ): { unsubscribe: () => void } {
    return this.events.on(event, callback);
  }

  public dispose(): void {
    if (this.isDisposed) return;
    this.isDisposed = true;
    
    this.logger.info('Disposing ConnectionManager');
    
    this.disconnect('dispose');
    
    this.heartbeat.dispose();
    this.resilience.dispose();
    
    this.events.clear();
    
    this.logger.info('ConnectionManager disposed');
  }

}