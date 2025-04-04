// src/services/connection/connection-manager.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { ExchangeDataStream } from '../sse/exchange-data-stream';
import { SessionApi } from '../../api/session';
import { HttpClient } from '../../api/http-client';
import { RecoveryManager } from './recovery-manager';
export { ConnectionState } from './connection-state';
import { ConnectionLifecycleManager } from './connection-lifecycle';
import { ConnectionDataHandlers } from './connection-data-handlers';
import { ConnectionSimulatorManager } from './connection-simulator';

export class ConnectionManager extends EventEmitter {
  private lifecycleManager: ConnectionLifecycleManager;
  private dataHandlers: ConnectionDataHandlers;
  private simulatorManager: ConnectionSimulatorManager;
  private recoveryManager: RecoveryManager;
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
    this.recoveryManager = new RecoveryManager(this, tokenManager);

    this.setupEventListeners();
  }

  private setupEventListeners(): void {
    this.wsManager.on('connected', () => {
      this.emit('connected');
      this.connectSSE().catch(err => 
        console.error('Failed to connect SSE after WebSocket connected:', err)
      );
    });
    
    this.wsManager.on('disconnected', (data) => {
      this.emit('disconnected', data);
      this.sseManager.disconnect();
    });
    
    this.wsManager.on('reconnecting', (data) => {
      this.emit('reconnecting', data);
    });
    
    this.wsManager.on('heartbeat', (data) => {
      this.emit('heartbeat', data);
    });

    this.sseManager.on('exchange-data', (data) => {
      this.dataHandlers.updateExchangeData(data);
      this.emit('exchange_data', data);
    });
    
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

  public async connect(): Promise<boolean> {
    try {
      const wsConnected = await this.wsManager.connect();
      if (!wsConnected) {
        return false;
      }
      
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

  public getState() {
    const wsHealth = this.wsManager.getConnectionHealth();
    return {
      isConnected: wsHealth.status === 'connected',
      isConnecting: wsHealth.status === 'connecting',
      connectionQuality: wsHealth.quality || 'unknown',
      error: wsHealth.error || null
    };
  }

  public getExchangeData() {
    return this.dataHandlers.getExchangeData();
  }

  public updateRecoveryAuthState(isAuthenticated: boolean): void {
    if (!isAuthenticated) {
      this.disconnect();
    }
    this.recoveryManager.updateAuthState(isAuthenticated);
  }

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

  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    return this.recoveryManager.attemptRecovery(reason);
  }
  
  public async reconnect(): Promise<boolean> {
    this.disconnect();
    return this.connect();
  }

  public addWSEventListener(event: string, handler: Function): void {
    this.wsManager.on(event, handler);
  }

  public removeWSEventListener(event: string, handler: Function): void {
    this.wsManager.off(event, handler);
  }

  public addSSEEventListener(event: string, handler: Function): void {
    this.sseManager.on(event, handler);
  }

  public removeSSEEventListener(event: string, handler: Function): void {
    this.sseManager.off(event, handler);
  }

  public dispose(): void {
    this.disconnect();
    this.recoveryManager.dispose();
    this.removeAllListeners();
  }
}