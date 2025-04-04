// src/services/connection/connection-manager.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { ExchangeDataStream } from '../sse/exchange-data-stream';
import { SessionApi } from '../../api/session';
import { HttpClient } from '../../api/http-client';
import { ConnectionRecoveryInterface } from './connection-recovery-interface';
import { RecoveryManager } from './recovery-manager';
import { 
  UnifiedConnectionState, 
  ConnectionServiceType, 
  ConnectionStatus 
} from './unified-connection-state';
import { ConnectionDataHandlers } from './connection-data-handlers';
import { ConnectionSimulatorManager } from './connection-simulator';

export class ConnectionManager extends EventEmitter implements ConnectionRecoveryInterface {
  private unifiedState: UnifiedConnectionState;
  private dataHandlers: ConnectionDataHandlers;
  private simulatorManager: ConnectionSimulatorManager;
  private recoveryManager: RecoveryManager;
  private wsManager: WebSocketManager;
  private sseManager: ExchangeDataStream;
  private tokenManager: TokenManager;

  constructor(tokenManager: TokenManager) {
    super();
    
    this.tokenManager = tokenManager;
    
    // Create the unified state first
    this.unifiedState = new UnifiedConnectionState();

    // Create HTTP client
    const httpClient = new HttpClient(tokenManager);
    
    // Create WebSocket manager with unified state
    this.wsManager = new WebSocketManager(tokenManager, this.unifiedState);
    
    // Create session API client
    const sessionApi = new SessionApi(httpClient);
    
    // Create SSE manager with unified state and WebSocket
    this.sseManager = new ExchangeDataStream(tokenManager, this.wsManager, this.unifiedState);

    // Create data handlers
    this.dataHandlers = new ConnectionDataHandlers(httpClient);
    
    // Create simulator manager
    this.simulatorManager = new ConnectionSimulatorManager(httpClient);
    
    // Create recovery manager with unified state
    this.recoveryManager = new RecoveryManager(this, tokenManager, this.unifiedState);
    
    this.setupEventListeners();
  }

  private setupEventListeners(): void {
    // Forward unified state changes
    this.unifiedState.on('state_change', (state: any) => {
      this.emit('state_change', { current: state });
    });
    
    // Forward WebSocket connection events
    this.wsManager.on('connected', () => {
      this.emit('connected');
      // When WebSocket connects, ensure SSE is also connected
      this.connectSSE().catch(err => 
        console.error('Failed to connect SSE after WebSocket connected:', err)
      );
    });
    
    this.wsManager.on('disconnected', (data: any) => {
      this.emit('disconnected', data);
    });
    
    this.wsManager.on('heartbeat', (data: any) => {
      this.emit('heartbeat', data);
    });

    // Set up data handlers for SSE events
    this.sseManager.on('exchange-data', (data: any) => {
      this.dataHandlers.updateExchangeData(data);
      this.emit('exchange_data', data);
    });
    
    // Recovery events
    this.recoveryManager.on('recovery_attempt', (data: any) => {
      this.emit('recovery_attempt', data);
    });
    
    this.recoveryManager.on('recovery_success', () => {
      this.emit('recovery_success');
    });
    
    this.recoveryManager.on('recovery_failed', () => {
      this.emit('recovery_failed');
    });
  }
  
  // Add proper cleanup method
  public dispose(): void {
    this.disconnect();
    
    // Clean up managers that implement Disposable
    this.recoveryManager.dispose();
    
    if ('dispose' in this.wsManager) {
      this.wsManager.dispose();
    }
    
    if ('dispose' in this.sseManager) {
      this.sseManager.dispose();
    }
        
    // Similarly in WebSocketManager
    if ('dispose' in this.metricTracker) {
      this.metricTracker.dispose();
    }

    // Clean up auth state monitoring
    if (this.tokenManager) {
      this.tokenManager.removeRefreshListener(this.handleTokenRefresh);
    }
    
    // Remove all event listeners
    super.dispose();
  }

  private async connectSSE(): Promise<boolean> {
    // Only connect SSE if WebSocket is connected
    const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    if (wsState.status === ConnectionStatus.CONNECTED) {
      return this.sseManager.connect();
    }
    return false;
  }

  // Lifecycle Methods - WebSocket is the primary connection
  public async connect(): Promise<boolean> {
    try {
      // First connect WebSocket
      const wsConnected = await this.wsManager.connect();
      if (!wsConnected) {
        return false;
      }
      
      // WebSocket connected - SSE will be connected automatically via event listener
      return true;
    } catch (error) {
      console.error('Connection error:', error);
      return false;
    }
  }

  public disconnect(): void {
    this.wsManager.disconnect();
    this.sseManager.disconnect();
    this.unifiedState.reset();
  }

  // Method to update recovery auth state
  public updateRecoveryAuthState(isAuthenticated: boolean): void {
    if (!isAuthenticated) {
      this.disconnect();
    }
    this.recoveryManager.updateAuthState(isAuthenticated);
  }

  private handleTokenRefresh = (success: boolean) => {
    this.updateRecoveryAuthState(success && this.tokenManager.isAuthenticated());
    
    // If token refresh failed, disconnect
    if (!success) {
      this.disconnect();
      this.emit('auth_failed', 'Authentication token expired');
    }
  };

  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    return this.recoveryManager.attemptRecovery(reason);
  }

  public getState() {
    return this.unifiedState.getState();
  }

  // Data Retrieval Methods
  public getExchangeData() {
    return this.dataHandlers.getExchangeData();
  }

  // Order Management Methods
  public async submitOrder(order: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price?: number;
    type: 'MARKET' | 'LIMIT';
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
    const state = this.getState();
    if (!state.isConnected) {
      return { success: false, error: 'Not connected to trading servers' };
    }

    return this.dataHandlers.submitOrder(order);
  }

  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
    const state = this.getState();
    if (!state.isConnected) {
      return { success: false, error: 'Not connected to trading servers' };
    }

    return this.dataHandlers.cancelOrder(orderId);
  }

  // Simulator Methods
  public async startSimulator(options: {
    initialSymbols?: string[],
    initialCash?: number
  } = {}): Promise<{ success: boolean; status?: string; error?: string }> {
    const state = this.getState();
    if (!state.isConnected) {
      return { success: false, error: 'Not connected to trading servers' };
    }

    return this.simulatorManager.startSimulator(options);
  }

  public async stopSimulator(): Promise<{ success: boolean; error?: string }> {
    const state = this.getState();
    if (!state.isConnected) {
      return { success: false, error: 'Not connected to trading servers' };
    }

    return this.simulatorManager.stopSimulator();
  }

  public async getSimulatorStatus(): Promise<{ success: boolean; status: string; error?: string }> {
    return this.simulatorManager.getSimulatorStatus();
  }
    
  // Reconnection method
  public async reconnect(): Promise<boolean> {
    // First disconnect everything cleanly
    this.disconnect();
    
    // Then reconnect
    return this.connect();
  }

  // Manual reconnect method (user-initiated)
  public async manualReconnect(): Promise<boolean> {
    // Reset recovery attempts in the unified state
    this.unifiedState.updateRecovery(true, 1);
    
    return this.attemptRecovery('manual_user_request');
  }

  // WebSocket Event Listeners
  public addWSEventListener(event: string, handler: Function): void {
    this.wsManager.on(event, handler);
  }

  public removeWSEventListener(event: string, handler: Function): void {
    this.wsManager.off(event, handler);
  }

  // SSE Event Listeners
  public addSSEEventListener(event: string, handler: Function): void {
    this.sseManager.on(event, handler);
  }

  public removeSSEEventListener(event: string, handler: Function): void {
    this.sseManager.off(event, handler);
  }
}