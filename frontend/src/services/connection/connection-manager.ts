// src/services/connection/connection-manager.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { ExchangeDataStream } from '../sse/exchange-data-stream';
import { SessionApi } from '../../api/session';
import { HttpClient } from '../../api/http-client';
import { RecoveryManager } from './recovery-manager';

import { ConnectionLifecycleManager } from './connection-lifecycle';
import { ConnectionDataHandlers } from './connection-data-handlers';
import { ConnectionSimulatorManager } from './connection-simulator';

export class ConnectionManager extends EventEmitter {
  private lifecycleManager: ConnectionLifecycleManager;
  private dataHandlers: ConnectionDataHandlers;
  private simulatorManager: ConnectionSimulatorManager;
  private recoveryManager: RecoveryManager;

  constructor(tokenManager: TokenManager) {
    super();

    const httpClient = new HttpClient(tokenManager);
    const wsManager = new WebSocketManager(tokenManager);
    const sessionApi = new SessionApi(httpClient, tokenManager);
    const sseManager = new ExchangeDataStream(tokenManager, wsManager);

    this.lifecycleManager = new ConnectionLifecycleManager(
      tokenManager, wsManager, sseManager, sessionApi, httpClient
    );

    this.dataHandlers = new ConnectionDataHandlers(httpClient);
    this.simulatorManager = new ConnectionSimulatorManager(httpClient);
    this.recoveryManager = new RecoveryManager(this, tokenManager);

    this.setupEventListeners();
  }

  private setupEventListeners(): void {
    // Forward lifecycle events
    this.lifecycleManager.on('connected', () => this.emit('connected'));
    this.lifecycleManager.on('disconnected', () => this.emit('disconnected'));
    this.lifecycleManager.on('heartbeat', (data) => this.emit('heartbeat', data));

    // Set up data handlers for SSE events
    this.lifecycleManager.on('market-data-updated', (data) => {
      this.dataHandlers.updateMarketData(data);
      this.emit('market_data', data);
    });

    this.lifecycleManager.on('orders-updated', (data) => {
      this.dataHandlers.updateOrders(data);
      this.emit('orders', data);
    });

    this.lifecycleManager.on('portfolio-updated', (data) => {
      this.dataHandlers.updatePortfolio(data);
      this.emit('portfolio', data);
    });
  }

  // Lifecycle Methods
  public async connect(): Promise<boolean> {
    return this.lifecycleManager.connect();
  }

  public disconnect(): void {
    this.lifecycleManager.disconnect();
  }

  public getState() {
    return this.lifecycleManager.getState();
  }

  // Data Retrieval Methods
  public getMarketData() {
    return this.dataHandlers.getMarketData();
  }

  public getOrders() {
    return this.dataHandlers.getOrders();
  }

  public getPortfolio() {
    return this.dataHandlers.getPortfolio();
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
    if (!state.sessionId) {
      return { success: false, error: 'No active session' };
    }

    return this.dataHandlers.submitOrder(state.sessionId, order);
  }

  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
    const state = this.getState();
    if (!state.sessionId) {
      return { success: false, error: 'No active session' };
    }

    return this.dataHandlers.cancelOrder(state.sessionId, orderId);
  }

  // Simulator Methods
  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    const state = this.getState();
    if (!state.isConnected) {
      return { success: false, error: 'Not connected' };
    }

    return this.simulatorManager.startSimulator();
  }

  public async stopSimulator(): Promise<{ success: boolean; error?: string }> {
    const state = this.getState();
    if (!state.isConnected) {
      return { success: false, error: 'Not connected' };
    }

    return this.simulatorManager.stopSimulator();
  }

  public async getSimulatorStatus(): Promise<{ success: boolean; status: string; error?: string }> {
    return this.simulatorManager.getSimulatorStatus();
  }

  // Recovery Methods
  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    return this.recoveryManager.attemptRecovery(reason);
  }

  // WebSocket and SSE Event Listeners
  public addWSEventListener(event: string, handler: Function): void {
    this.lifecycleManager.on(event, handler);
  }

  public removeWSEventListener(event: string, handler: Function): void {
    this.lifecycleManager.off(event, handler);
  }

  public addSSEEventListener(event: string, handler: Function): void {
    this.lifecycleManager.on(event, handler);
  }

  public removeSSEEventListener(event: string, handler: Function): void {
    this.lifecycleManager.off(event, handler);
  }

  // Cleanup Method
  public dispose(): void {
    this.disconnect();
    this.recoveryManager.dispose();
    this.removeAllListeners();
  }
}