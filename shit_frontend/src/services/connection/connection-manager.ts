// src/services/connection/connection-manager.ts
import { BehaviorSubject } from 'rxjs';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { HttpClient } from '../../api/http-client';
import { ConnectionRecoveryInterface } from './connection-recovery-interface';
import { ConnectionResilienceManager, ResilienceState } from './connection-resilience-manager';
import { WebSocketOptions } from '../websocket/types';
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus,
  ConnectionQuality
} from './unified-connection-state';
import { ConnectionDataHandlers } from './connection-data-handlers';
import { ConnectionSimulatorManager } from './connection-simulator';
import { Disposable } from '../../utils/disposable';
import { SessionApi } from '../../api/session';
import { AppErrorHandler } from '../../utils/app-error-handler';
import { ErrorSeverity } from '../../utils/error-handler';
import { OrderSide, OrderType } from '../../api/order';
import { TypedEventEmitter } from '../utils/typed-event-emitter';
import { getLogger } from '../../boot/logging';
import { appState } from '../state/app-state.service';

// Define event types for ConnectionManager
export interface ConnectionEvents {
  state_change: { current: ReturnType<UnifiedConnectionState['getState']> };
  connected: void;
  disconnected: { reason: string };
  recovery_attempt: { attempt: number; maxAttempts: number; delay: number; when: number };
  recovery_success: void;
  recovery_failed: { attempt: number; maxAttempts: number };
  max_reconnect_attempts: { attempts: number; maxAttempts: number };
  auth_failed: string;
  exchange_data: Record<string, any>;
  portfolio_data: Record<string, any>;
  risk_data: Record<string, any>;
  order_update: any;
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
    resetTimeoutMs?: number;
    failureThreshold?: number;
  };
}

/**
 * Central manager for all connection-related functionality
 */
export class ConnectionManager extends TypedEventEmitter<ConnectionEvents> implements ConnectionRecoveryInterface, Disposable {
  private unifiedState: UnifiedConnectionState;
  private dataHandlers: ConnectionDataHandlers;
  private simulatorManager: ConnectionSimulatorManager;
  private resilienceManager: ConnectionResilienceManager;
  private wsManager: WebSocketManager;
  private tokenManager: TokenManager;
  private logger = getLogger('ConnectionManager');
  private isDisposed: boolean = false;
  private sessionApi: SessionApi;
  private httpClient: HttpClient;
  
  // Data storage
  private exchangeData: Record<string, any> = {};
  private portfolioData: Record<string, any> = {};
  private riskData: Record<string, any> = {};
  
  // Current desired state
  private desiredState: ConnectionDesiredState = {
    connected: false,
    simulatorRunning: false
  };
  
  // State change subject
  private stateChange$ = new BehaviorSubject<ReturnType<UnifiedConnectionState['getState']> | null>(null);
  
  constructor(
    tokenManager: TokenManager,
    options: ConnectionManagerOptions = {}
  ) {
    super('ConnectionManager');
    
    this.logger.info('ConnectionManager initializing...', { options });
    
    // Store dependencies
    this.tokenManager = tokenManager;
    
    // Verify authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Initializing ConnectionManager without active authentication');
    }
    
    // Initialize state management
    this.unifiedState = new UnifiedConnectionState();
    
    // Initialize HTTP client and APIs
    this.httpClient = new HttpClient(tokenManager);
    this.sessionApi = new SessionApi(this.httpClient);
    
    // Initialize websocket manager
    this.wsManager = new WebSocketManager(
      tokenManager,
      this.unifiedState,
      {
        ...options.wsOptions,
        preventAutoConnect: true
      }
    );
    
    // Initialize resilience manager
    this.resilienceManager = new ConnectionResilienceManager(
      tokenManager,
      options.resilience
    );
    
    // Initialize other managers
    this.dataHandlers = new ConnectionDataHandlers(this.httpClient, AppErrorHandler.getInstance());
    this.simulatorManager = new ConnectionSimulatorManager(this.httpClient);
    
    // Set up event listeners
    this.setupEventListeners();
    
    this.logger.info('ConnectionManager initialized');
  }
  
  /**
   * Sets up event listeners for various components
   */
  private setupEventListeners(): void {
    this.logger.info('Setting up ConnectionManager event listeners');
    
    // State change listener
    this.unifiedState.on('state_change', (state: ReturnType<UnifiedConnectionState['getState']>) => {
      if (this.isDisposed) return;
      
      // Update the state subject
      this.stateChange$.next(state);
      
      // Update the reactive app state
      appState.updateConnection({
        status: state.overallStatus,
        quality: state.connectionQuality,
        isRecovering: state.isRecovering,
        recoveryAttempt: state.recoveryAttempt,
        lastHeartbeatTime: state.lastHeartbeatTime,
        heartbeatLatency: state.heartbeatLatency,
        simulatorStatus: state.simulatorStatus
      });
      
      this.emit('state_change', { current: state });
      
      // Emit derived events
      if (!this.isDisposed) {
        if (state.overallStatus === ConnectionStatus.CONNECTED) {
          this.emit('connected', undefined);
          
          // Auto-start simulator if desired
          if (this.desiredState.simulatorRunning) {
            this.syncSimulatorState();
          }
        } else if (state.overallStatus === ConnectionStatus.DISCONNECTED) {
          const reason = state.webSocketState.error || 'disconnected';
          this.emit('disconnected', { reason });
        }
      }
    });
    
    // WebSocket event listeners
    this.wsManager.subscribe('exchange_data', (data: any) => {
      if (this.isDisposed) return;
      this.exchangeData = { ...this.exchangeData, ...data };
      
      // Update the reactive state
      appState.updateExchangeData(data);
      
      this.emit('exchange_data', data);
    });
    
    this.wsManager.subscribe('portfolio_data', (data: any) => {
      if (this.isDisposed) return;
      this.portfolioData = { ...this.portfolioData, ...data };
      
      // Update the reactive state with portfolio data
      appState.updatePortfolio({
        positions: data.positions || {},
        cash: data.cash || 0
      });
      
      this.emit('portfolio_data', data);
    });
    
    this.wsManager.subscribe('risk_data', (data: any) => {
      if (this.isDisposed) return;
      this.riskData = { ...this.riskData, ...data };
      this.emit('risk_data', data);
    });
    
    this.wsManager.subscribe('order_update', (data: any) => {
      if (this.isDisposed) return;
      this.emit('order_update', data);
      
      // Update portfolio orders in the reactive state
      appState.updatePortfolio({
        orders: {
          ...appState.getState().portfolio.orders,
          [data.orderId]: data
        }
      });
    });
    
    // Resilience manager events
    this.resilienceManager.subscribe('reconnect_scheduled', (data: any) => {
      if (this.isDisposed) return;
      this.logger.info(`Reconnection scheduled: attempt ${data.attempt}/${data.maxAttempts} in ${data.delay}ms`);
      this.unifiedState.updateRecovery(true, data.attempt);
      this.emit('recovery_attempt', data);
    });
    
    this.resilienceManager.subscribe('reconnect_success', () => {
      if (this.isDisposed) return;
      this.logger.info('Connection recovery successful');
      this.unifiedState.updateRecovery(false, 0);
      this.emit('recovery_success', undefined);
    });
    
    this.resilienceManager.subscribe('reconnect_failure', (data: any) => {
      if (this.isDisposed) return;
      this.logger.error('Connection recovery failed', data);
      this.emit('recovery_failed', data);
    });
    
    this.resilienceManager.subscribe('max_attempts_reached', (data: any) => {
      if (this.isDisposed) return;
      this.logger.error(`Maximum reconnection attempts (${data.maxAttempts}) reached`);
      this.unifiedState.updateRecovery(false, data.attempts);
      this.emit('max_reconnect_attempts', data);
    });
    
    // Authentication listener
    this.tokenManager.addRefreshListener(this.handleTokenRefresh);
    
    this.logger.info('ConnectionManager event listeners setup complete');
  }
  
  /**
   * Sets the desired state of the connection and simulator
   * This allows for a more declarative API
   */
  public setDesiredState(state: Partial<ConnectionDesiredState>): void {
    if (this.isDisposed) {
      this.logger.error('Cannot set desired state: ConnectionManager is disposed');
      return;
    }
    
    const oldState = { ...this.desiredState };
    this.desiredState = { ...this.desiredState, ...state };
    
    this.logger.info('Desired state updated', { 
      oldState, 
      newState: this.desiredState 
    });
    
    // Synchronize actual state with desired state
    this.syncConnectionState();
    this.syncSimulatorState();
  }
  
  /**
   * Synchronizes the connection state with the desired state
   */
  private syncConnectionState(): void {
    if (this.isDisposed) return;
    
    const currentStatus = this.unifiedState.getState().overallStatus;
    const isConnected = currentStatus === ConnectionStatus.CONNECTED;
    
    if (this.desiredState.connected && !isConnected &&
        currentStatus !== ConnectionStatus.CONNECTING &&
        currentStatus !== ConnectionStatus.RECOVERING) {
      // We want to be connected but we're not - connect
      this.logger.info('Syncing connection state: attempting to connect');
      this.connect().catch(err => {
        this.logger.error('Failed to connect during state sync', { error: err.message });
      });
    } else if (!this.desiredState.connected && isConnected) {
      // We don't want to be connected but we are - disconnect
      this.logger.info('Syncing connection state: disconnecting');
      this.disconnect('desired_state_change');
    }
  }
  
  /**
   * Synchronizes the simulator state with the desired state
   */
  private async syncSimulatorState(): Promise<void> {
    if (this.isDisposed) return;
    
    const isConnected = this.unifiedState.getState().overallStatus === ConnectionStatus.CONNECTED;
    if (!isConnected) return;
    
    const currentStatus = this.unifiedState.getState().simulatorStatus;
    const isRunning = currentStatus === 'RUNNING';
    
    if (this.desiredState.simulatorRunning && !isRunning &&
        currentStatus !== 'STARTING' && currentStatus !== 'STOPPING') {
      // We want simulator running but it's not - start it
      this.logger.info('Syncing simulator state: attempting to start simulator');
      try {
        await this.startSimulator();
      } catch (err) {
        this.logger.error('Failed to start simulator during state sync', { error: err instanceof Error ? err.message : String(err) });
      }
    } else if (!this.desiredState.simulatorRunning && isRunning) {
      // We don't want simulator running but it is - stop it
      this.logger.info('Syncing simulator state: stopping simulator');
      try {
        await this.stopSimulator();
      } catch (err) {
        this.logger.error('Failed to stop simulator during state sync', { error: err instanceof Error ? err.message : String(err) });
      }
    }
  }
  
  /**
   * Attempts to establish a connection by validating the session and connecting WebSocket
   */
  public async connect(): Promise<boolean> {
    return this.logger.trackTime('connect', async () => {
      if (this.isDisposed) {
        this.logger.error('Cannot connect: ConnectionManager is disposed');
        return false;
      }
      
      if (!this.tokenManager.isAuthenticated()) {
        this.logger.error('Cannot connect: Not authenticated');
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.DISCONNECTED,
          error: 'Authentication required'
        });
        return false;
      }
      
      // Update desired state
      this.desiredState.connected = true;
      
      const currentState = this.unifiedState.getState();
      if (currentState.isConnected) {
        this.logger.info('Already connected');
        return true;
      }
      
      if (currentState.isConnecting || currentState.isRecovering) {
        this.logger.warn(`Connect call ignored: Already ${currentState.overallStatus}`);
        return false;
      }
      
      try {
        this.logger.info('Attempting to create or validate session');
        
        // Update state to connecting
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.CONNECTING,
          error: null
        });
        
        // Validate session
        const sessionResponse = await this.sessionApi.createSession();
        
        if (this.isDisposed) {
          this.logger.warn('ConnectionManager disposed during session validation');
          return false;
        }
        
        if (!sessionResponse.success) {
          const errorMsg = sessionResponse.errorMessage || 'Failed to establish session with server';
          throw new Error(`Session Error: ${errorMsg}`);
        }
        
        this.logger.info('Session validated successfully');
        
        // Connect WebSocket
        const wsConnected = await this.wsManager.connect();
        
        if (this.isDisposed) {
          this.logger.warn('ConnectionManager disposed during WebSocket connection');
          this.wsManager.disconnect('disposed_during_connect');
          return false;
        }
        
        if (!wsConnected) {
          this.logger.error('WebSocket connection failed after session validation');
          return false;
        }
        
        return true;
        
      } catch (error) {
        if (this.isDisposed) {
          this.logger.warn('Connection process failed, but ConnectionManager was disposed');
          return false;
        }
        
        this.logger.error('Connection process failed', { error });
        
        // Update state
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.DISCONNECTED,
          error: error instanceof Error ? error.message : String(error)
        });
        
        // Record failure in resilience manager
        this.resilienceManager.recordFailure(error);
        
        // Handle error
        AppErrorHandler.handleConnectionError(
          error instanceof Error ? error : String(error),
          ErrorSeverity.HIGH,
          'ConnectionManager.connect'
        );
        
        return false;
      }
    });
  }
  
  /**
   * Disconnects the WebSocket connection
   */
  public disconnect(reason: string = 'manual_disconnect'): void {
    if (this.isDisposed && reason !== 'manager_disposed') {
      this.logger.info(`Disconnect called on disposed ConnectionManager. Reason: ${reason}`);
      return;
    }
    
    // Update desired state unless it's an internal reason
    if (!reason.startsWith('internal_')) {
      this.desiredState.connected = false;
    }
    
    this.logger.warn(`Disconnecting. Reason: ${reason}`);
    this.wsManager.disconnect(reason);
  }
  
  /**
   * Handles token refresh events
   */
  private handleTokenRefresh = (success: boolean): void => {
    if (this.isDisposed) return;
    
    this.logger.info(`Token refresh result: ${success ? 'success' : 'failure'}`);
    
    const isAuthenticated = success && this.tokenManager.isAuthenticated();
    
    // Update resilience manager with auth state
    this.resilienceManager.updateAuthState(isAuthenticated);
    
    if (!isAuthenticated) {
      this.logger.error('Authentication lost, forcing disconnect');
      this.disconnect('auth_lost');
      
      AppErrorHandler.handleAuthError(
        'Session expired or token refresh failed',
        ErrorSeverity.HIGH,
        'TokenRefresh'
      );
      
      this.emit('auth_failed', 'Authentication token expired or refresh failed');
    }
  };
  
  /**
   * Initiates a connection recovery attempt
   */
  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    if (this.isDisposed) {
      this.logger.error('Cannot attempt recovery: ConnectionManager is disposed');
      return false;
    }
    
    this.logger.warn(`Connection recovery requested. Reason: ${reason}`);
    
    // Ensure desired state reflects intention to connect
    this.desiredState.connected = true;
    
    // Use the resilience manager's reconnection mechanism
    return this.resilienceManager.attemptReconnection(async () => {
      return this.connect();
    });
  }
  
  /**
   * Gets the current connection state
   */
  public getState(): ReturnType<UnifiedConnectionState['getState']> {
    if (this.isDisposed) {
      this.logger.warn('getState called on disposed ConnectionManager');
      const defaultState = new UnifiedConnectionState();
      const state = defaultState.getState();
      defaultState.dispose();
      return state;
    }
    
    return this.unifiedState.getState();
  }
  
  /**
   * Gets an observable of the connection state
   */
  public getStateObservable() {
    return this.stateChange$.asObservable();
  }
  
  /**
   * Gets the current exchange data
   */
  public getExchangeData(): Record<string, any> {
    if (this.isDisposed) return {};
    return { ...this.exchangeData };
  }
  
  /**
   * Gets the current portfolio data
   */
  public getPortfolioData(): Record<string, any> {
    if (this.isDisposed) return {};
    return { ...this.portfolioData };
  }
  
  /**
   * Gets the current risk data
   */
  public getRiskData(): Record<string, any> {
    if (this.isDisposed) return {};
    return { ...this.riskData };
  }
  
  /**
   * Submits a trading order
   */
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
    return this.dataHandlers.submitOrder(order);
  }
  
  /**
   * Cancels a trading order
   */
  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    
    const state = this.getState();
    if (!state.isConnected) {
      const errorMsg = 'Cancel order failed: Not connected to trading servers';
      this.logger.error(errorMsg, { state });
      return { success: false, error: errorMsg };
    }
    
    this.logger.info('Cancelling order', { orderId });
    return this.dataHandlers.cancelOrder(orderId);
  }
  
  /**
   * Starts the trading simulator
   */
  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    
    // Update desired state
    this.desiredState.simulatorRunning = true;
    
    const state = this.getState();
    if (!state.isConnected) {
      const errorMsg = 'Start simulator failed: Not connected to trading servers';
      this.logger.error(errorMsg, { state });
      return { success: false, error: errorMsg };
    }
    
    this.logger.info('Starting simulator');
    const result = await this.simulatorManager.startSimulator();
    
    if (!result.success) {
      this.desiredState.simulatorRunning = false;
    }
    
    return result;
  }
  
  /**
   * Stops the trading simulator
   */
  public async stopSimulator(): Promise<{ success: boolean; error?: string }> {
    if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    
    // Update desired state
    this.desiredState.simulatorRunning = false;
    
    const state = this.getState();
    if (!state.isConnected) {
      const errorMsg = 'Stop simulator failed: Not connected to trading servers';
      this.logger.error(errorMsg, { state });
      return { success: false, error: errorMsg };
    }
    
    this.logger.info('Stopping simulator');
    return this.simulatorManager.stopSimulator();
  }
  
  /**
   * Initiates a manual reconnection attempt
   * This is a simplified API for users compared to the more detailed attemptRecovery
   */
  public async manualReconnect(): Promise<boolean> {
    if (this.isDisposed) {
      this.logger.error('Cannot reconnect: ConnectionManager is disposed');
      return false;
    }
    
    this.logger.warn('Manual reconnect requested by user');
    this.unifiedState.updateRecovery(true, 1);
    return this.attemptRecovery('manual_user_request');
  }
  
  /**
   * Implements ConnectionRecoveryInterface.getState
   */
  getStateForRecovery(): { isConnected: boolean; isConnecting: boolean } {
    const state = this.getState();
    return {
      isConnected: state.isConnected,
      isConnecting: state.isConnecting || state.isRecovering
    };
  }
  
  /**
   * Disposes of resources
   */
  public dispose(): void {
    if (this.isDisposed) {
      this.logger.warn('ConnectionManager already disposed');
      return;
    }
    
    this.logger.warn('Disposing ConnectionManager');
    this.isDisposed = true;
    
    // Unsubscribe from token refresh events
    if (this.tokenManager) {
      try {
        this.tokenManager.removeRefreshListener(this.handleTokenRefresh);
      } catch (error) {
        this.logger.error('Error removing token refresh listener during dispose', { error });
      }
    }
    
    // Complete the state subject
    this.stateChange$.complete();
    
    // Disconnect WebSocket
    this.disconnect('manager_disposed');
    
    // Dispose components
    this.resilienceManager.dispose();
    this.wsManager.dispose();
    this.unifiedState.dispose();
    
    // Clear data
    this.exchangeData = {};
    this.portfolioData = {};
    this.riskData = {};
    
    // Remove event listeners
    super.dispose();
    
    this.logger.info('ConnectionManager disposed');
  }
  
  /**
   * Implements the Symbol.dispose method for the Disposable interface
   */
  [Symbol.dispose](): void {
    this.dispose();
  }
}