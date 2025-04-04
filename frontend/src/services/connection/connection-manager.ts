import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { ExchangeDataStream } from '../sse/exchange-data-stream';
import { SessionApi } from '../../api/session';
import { HttpClient } from '../../api/http-client';
import { ConnectionRecoveryInterface } from './connection-recovery-interface';
import { RecoveryManager } from './recovery-manager';
export { ConnectionState } from './connection-state';
import { ConnectionLifecycleManager } from './connection-lifecycle';
import { ConnectionDataHandlers } from './connection-data-handlers';
import { ConnectionSimulatorManager } from './connection-simulator';

export class ConnectionManager extends EventEmitter implements ConnectionRecoveryInterface {
  private lifecycleManager: ConnectionLifecycleManager;
  private dataHandlers: ConnectionDataHandlers;
  private simulatorManager: ConnectionSimulatorManager;
  private recoveryManager: RecoveryManager | null = null;
  private wsManager: WebSocketManager;
  private sseManager: ExchangeDataStream;

  constructor(tokenManager: TokenManager) {
    super();

    const httpClient = new HttpClient(tokenManager);
    this.wsManager = new WebSocketManager(tokenManager);
    const sessionApi = new SessionApi(httpClient, tokenManager);
    this.sseManager = new ExchangeDataStream(tokenManager, this.wsManager);

    this.lifecycleManager = new ConnectionLifecycleManager(
      tokenManager, this.wsManager, this.sseManager, sessionApi, httpClient
    );

    this.dataHandlers = new ConnectionDataHandlers(httpClient);
    this.simulatorManager = new ConnectionSimulatorManager(httpClient);
    
    this.setupEventListeners();
    
    // Initialize RecoveryManager after ConnectionManager is fully set up
    setTimeout(() => {
      this.recoveryManager = new RecoveryManager(this, tokenManager);
      this.setupRecoveryEventListeners();
    }, 0);
  }

  private setupEventListeners(): void {
    // Forward WebSocket connection events to determine overall connection status
    this.wsManager.on('connected', () => {
      this.emit('connected');
      // When WebSocket connects, ensure SSE is also connected
      this.connectSSE().catch(err => 
        console.error('Failed to connect SSE after WebSocket connected:', err)
      );
    });
    
    this.wsManager.on('disconnected', (data) => {
      this.emit('disconnected', data);
      // Disconnect SSE when WebSocket disconnects
      this.sseManager.disconnect();
    });
    
    this.wsManager.on('reconnecting', (data) => {
      this.emit('reconnecting', data);
    });
    
    this.wsManager.on('heartbeat', (data) => {
      this.emit('heartbeat', data);
    });

    // Set up data handlers for SSE events - using new exchangeData structure
    this.sseManager.on('exchange-data', (data) => {
      this.dataHandlers.updateExchangeData(data);
      this.emit('exchange_data', data);
    });
    
    // Recovery events
    this.recoveryManager.on('recovery_attempt', (data) => {
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
    if (this.recoveryManager) {
      this.recoveryManager.dispose();
    }
    
    if (this.wsManager instanceof Disposable) {
      this.wsManager.dispose();
    }
    
    if (this.sseManager instanceof Disposable) {
      this.sseManager.dispose();
    }
    
    // Clean up auth state monitoring
    if (this.tokenManager) {
      this.tokenManager.removeRefreshListener(this.handleTokenRefresh);
    }
    
    // Remove all event listeners
    super.dispose();
  }

  private setupRecoveryEventListeners(): void {
    if (!this.recoveryManager) return;
    
    // Set up event listeners for recovery events
    this.recoveryManager.on('recovery_attempt', (data) => {
      this.emit('recovery_attempt', data);
    });
    
    this.recoveryManager.on('recovery_success', () => {
      this.emit('recovery_success');
    });
    
    this.recoveryManager.on('recovery_failed', () => {
      this.emit('recovery_failed');
    });
  }

  private async connectSSE(): Promise<boolean> {
    if (this.wsManager.getConnectionHealth().status === 'connected') {
      return this.sseManager.connect();
    }
    return false;
  }

  // Lifecycle Methods - make WebSocket the primary connection
  public async connect(): Promise<boolean> {
    try {
      // First connect WebSocket
      const wsConnected = await this.wsManager.connect();
      if (!wsConnected) {
        return false;
      }
      
      // Then connect SSE if WebSocket connected
      await this.connectSSE();
      
      return true;
    } catch (error) {
      console.error('Connection error:', error);
      return false;
    }
  }

  public disconnect(): void {
    this.wsManager.disconnect();
    this.sseManager.disconnect();
  }

  // Method to update recovery auth state
  public updateRecoveryAuthState(isAuthenticated: boolean): void {
    if (!isAuthenticated) {
      this.disconnect();
    }
    this.recoveryManager?.updateAuthState(isAuthenticated);
  }

  // Setup auth state monitoring
  private setupAuthStateMonitoring(): void {
    // Add token refresh listener
    this.tokenManager.addRefreshListener((success: boolean) => {
      this.updateRecoveryAuthState(success && this.tokenManager.isAuthenticated());
      
      // If token refresh failed, disconnect
      if (!success) {
        this.disconnect();
        this.emit('auth_failed', 'Authentication token expired');
      }
    });
  }

  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    if (!this.recoveryManager) return false;
    return this.recoveryManager.attemptRecovery(reason);
  }

  public getState() {
    const wsHealth = this.wsManager.getConnectionHealth();
    return {
      isConnected: wsHealth.status === 'connected',
      isConnecting: wsHealth.status === 'connecting',
      connectionQuality: wsHealth.quality || 'unknown',
      simulatorStatus: this.lifecycleManager.getSimulatorStatus(),
      error: wsHealth.error || null
    };
  }

  // Data Retrieval Methods - now only exposing exchangeData
  public getExchangeData() {
    return this.dataHandlers.getExchangeData();
  }

  // Order Management Methods - submit and cancel orders
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
  
  // Reconnection method - primarily reconnect WebSocket
  public async reconnect(): Promise<boolean> {
    // First disconnect everything cleanly
    this.disconnect();
    
    // Then reconnect
    return this.connect();
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