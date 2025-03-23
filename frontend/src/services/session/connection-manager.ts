// src/services/session/connection-manager.ts
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/ws-manager';
import { MarketDataStream } from '../sse/market-data-stream';
import { SessionStore } from './session-store';
import { AuthApi } from '../../api/auth';
import { SessionApi } from '../../api/session';
import { OrdersApi } from '../../api/orders';
import { HttpClient } from '../../api/http-client';

export interface ConnectionState {
  isConnected: boolean;
  isConnecting: boolean;
  sessionId: string | null;
  simulatorId: string | null;
  simulatorStatus: string;
  connectionQuality: 'good' | 'degraded' | 'poor';
  lastHeartbeatTime: number;
  heartbeatLatency: number | null;
  podName: string | null;
  reconnectAttempt: number;
  error: string | null;
}

export class ConnectionManager {
  private tokenManager: TokenManager;
  private wsManager: WebSocketManager;
  private marketDataStream: MarketDataStream;
  private sessionApi: SessionApi;
  private ordersApi: OrdersApi;
  private sessionStore: SessionStore;
  
  private state: ConnectionState = {
    isConnected: false,
    isConnecting: false,
    sessionId: null,
    simulatorId: null,
    simulatorStatus: 'UNKNOWN',
    connectionQuality: 'good',
    lastHeartbeatTime: 0,
    heartbeatLatency: null,
    podName: null,
    reconnectAttempt: 0,
    error: null
  };
  
  private heartbeatInterval: number | null = null;
  private keepAliveInterval: number | null = null;
  private eventListeners: Map<string, Set<Function>> = new Map();
  
  constructor(
    baseApiUrl: string,
    wsUrl: string,
    sseUrl: string,
    tokenManager: TokenManager
  ) {
    this.tokenManager = tokenManager;
    
    // Create HTTP client
    const httpClient = new HttpClient(baseApiUrl, tokenManager);
    
    // Create API clients
    this.sessionApi = new SessionApi(httpClient);
    this.ordersApi = new OrdersApi(httpClient);
    
    // Create WebSocket manager
    this.wsManager = new WebSocketManager(wsUrl, tokenManager, {
      heartbeatInterval: 15000,
      reconnectMaxAttempts: 15
    });
    
    // Create Market Data stream
    this.marketDataStream = new MarketDataStream(tokenManager, {
      baseUrl: sseUrl,
      reconnectMaxAttempts: 15
    });
    
    // Set up event listeners
    this.setupEventListeners();
  }
  
  // Event handling
  public on(event: string, callback: Function): void {
    if (!this.eventListeners.has(event)) {
      this.eventListeners.set(event, new Set());
    }
    
    this.eventListeners.get(event)?.add(callback);
  }
  
  public off(event: string, callback: Function): void {
    const callbacks = this.eventListeners.get(event);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }
  
  private emit(event: string, data: any): void {
    const callbacks = this.eventListeners.get(event);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in connection manager event handler for ${event}:`, error);
        }
      });
    }
  }
  
  private setupEventListeners(): void {
    // WebSocket event listeners
    this.wsManager.on('connected', () => {
      this.updateState({ isConnected: true, error: null });
      this.emit('connected', { connected: true });
      this.startHeartbeat();
    });
    
    this.wsManager.on('disconnected', (data: any) => {
      this.updateState({ isConnected: false });
      this.emit('disconnected', data);
      this.stopHeartbeat();
    });
    
    this.wsManager.on('reconnecting', (data: any) => {
      this.updateState({ 
        isConnecting: true, 
        reconnectAttempt: data.attempt 
      });
      this.emit('reconnecting', data);
    });
    
    this.wsManager.on('heartbeat', (data: any) => {
      this.handleHeartbeat(data);
    });
    
    this.wsManager.on('error', (data: any) => {
      this.updateState({ error: data.error?.message || 'Connection error' });
      this.emit('error', data);
    });
    
    this.wsManager.on('simulator_status', (data: any) => {
      this.updateState({ 
        simulatorId: data.id || this.state.simulatorId,
        simulatorStatus: data.status || 'UNKNOWN'
      });
      this.emit('simulator_status', data);
    });
    
    // Market data stream listeners
    this.marketDataStream.on('market-data-updated', (data: any) => {
      this.emit('market_data', data);
    });
    
    this.marketDataStream.on('orders-updated', (data: any) => {
      this.emit('orders', data);
    });
    
    this.marketDataStream.on('portfolio-updated', (data: any) => {
      this.emit('portfolio', data);
    });
  }
  
  // Connection management
  public async connect(): Promise<boolean> {
    if (this.state.isConnected || this.state.isConnecting) {
      return this.state.isConnected;
    }
    
    this.updateState({ isConnecting: true, error: null });
    
    try {
      // Get session ID from store or create a new session
      let sessionId = SessionStore.getSessionId();
      
      if (!sessionId) {
        // Create a new session
        const response = await this.sessionApi.createSession();
        
        if (!response.success) {
          throw new Error(response.errorMessage || 'Failed to create session');
        }
        
        sessionId = response.sessionId;
        SessionStore.setSessionId(sessionId);
        
        // Update state with pod name if available
        if (response.podName) {
          this.updateState({ podName: response.podName });
        }
      }
      
      // Connect WebSocket
      const wsConnected = await this.wsManager.connect(sessionId);
      if (!wsConnected) {
        throw new Error('Failed to establish WebSocket connection');
      }
      
      // Get session state to get simulator info
      const sessionState = await this.sessionApi.getSessionState(sessionId);
      
      if (sessionState.success) {
        this.updateState({
          sessionId,
          simulatorId: sessionState.simulatorId,
          simulatorStatus: sessionState.simulatorStatus
        });
        
        // Store in session storage
        SessionStore.saveSession({
          sessionId,
          simulatorId: sessionState.simulatorId
        });
      }
      
      // Connect to market data stream
      await this.marketDataStream.connect(sessionId);
      
      // Start keep-alive interval
      this.startKeepAlive();
      
      this.updateState({ isConnected: true, isConnecting: false });
      return true;
    } catch (error) {
      console.error('Connection error:', error);
      this.updateState({ 
        isConnecting: false, 
        error: error instanceof Error ? error.message : 'Connection failed' 
      });
      return false;
    }
  }
  
  public disconnect(): void {
    // Stop intervals
    this.stopHeartbeat();
    this.stopKeepAlive();
    
    // Disconnect WebSocket
    this.wsManager.disconnect();
    
    // Disconnect market data stream
    this.marketDataStream.disconnect();
    
    // Clear session store
    SessionStore.clearSession();
    
    // Update state
    this.updateState({
      isConnected: false,
      isConnecting: false,
      sessionId: null,
      simulatorId: null,
      simulatorStatus: 'UNKNOWN',
      error: null
    });
  }
  
  public async reconnect(): Promise<boolean> {
    // Stop any existing connections
    this.stopHeartbeat();
    this.stopKeepAlive();
    
    this.updateState({ isConnecting: true, error: null });
    
    try {
      // Get session ID from store
      const sessionId = SessionStore.getSessionId();
      if (!sessionId) {
        // If no session ID, create a new session
        return this.connect();
      }
      
      const attempt = SessionStore.incrementReconnectAttempts();
      this.updateState({ reconnectAttempt: attempt });
      
      // Attempt to reconnect session
      const response = await this.sessionApi.reconnectSession(sessionId, attempt);
      
      if (!response.success) {
        throw new Error(response.errorMessage || 'Failed to reconnect session');
      }
      
      // Connect WebSocket
      const wsConnected = await this.wsManager.connect(response.sessionId);
      if (!wsConnected) {
        throw new Error('Failed to establish WebSocket connection');
      }
      
      // Connect to market data stream
      await this.marketDataStream.connect(response.sessionId);
      
      // Start intervals
      this.startHeartbeat();
      this.startKeepAlive();
      
      // Update state
      this.updateState({
        isConnected: true,
        isConnecting: false,
        sessionId: response.sessionId,
        simulatorId: response.simulatorId,
        simulatorStatus: response.simulatorStatus,
        error: null
      });
      
      // Store in session storage
      SessionStore.saveSession({
        sessionId: response.sessionId,
        simulatorId: response.simulatorId,
        reconnectAttempts: 0
      });
      
      return true;
    } catch (error) {
      console.error('Reconnection error:', error);
      this.updateState({ 
        isConnecting: false, 
        error: error instanceof Error ? error.message : 'Reconnection failed' 
      });
      return false;
    }
  }
  
  // Heartbeat and keep-alive
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    // Start heartbeat interval
    this.heartbeatInterval = window.setInterval(() => {
      // Send heartbeat via WebSocket
      this.wsManager.send({ type: 'heartbeat', timestamp: Date.now() });
    }, 15000); // Every 15 seconds
  }
  
  private stopHeartbeat(): void {
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
  
  private startKeepAlive(): void {
    this.stopKeepAlive();
    
    // Start keep-alive interval
    this.keepAliveInterval = window.setInterval(async () => {
      try {
        const sessionId = this.state.sessionId;
        if (!sessionId) return;
        
        // Send keep-alive to server
        const startTime = Date.now();
        const response = await this.sessionApi.keepAlive(sessionId);
        const latency = Date.now() - startTime;
        
        if (response.success) {
          // Update session store
          SessionStore.updateActivity();
          
          // Update heartbeat info
          this.handleHeartbeat({ timestamp: Date.now(), latency });
        }
      } catch (error) {
        console.error('Keep-alive error:', error);
      }
    }, 30000); // Every 30 seconds
  }
  
  private stopKeepAlive(): void {
    if (this.keepAliveInterval !== null) {
      clearInterval(this.keepAliveInterval);
      this.keepAliveInterval = null;
    }
  }
  
  private handleHeartbeat(data: any): void {
    this.updateState({
      lastHeartbeatTime: data.timestamp || Date.now(),
      heartbeatLatency: data.latency || this.state.heartbeatLatency
    });
    
    this.emit('heartbeat', {
      timestamp: data.timestamp || Date.now(),
      latency: data.latency
    });
  }
  
  // Connection quality
  public async updateConnectionQuality(): Promise<void> {
    try {
      const sessionId = this.state.sessionId;
      if (!sessionId) return;
      
      // Get metrics
      const latencyMs = this.state.heartbeatLatency || 0;
      const missedHeartbeats = Date.now() - this.state.lastHeartbeatTime > 30000 ? 1 : 0;
      const connectionType = 'websocket'; // or detect from browser
      
      // Send to server
      const response = await this.sessionApi.updateConnectionQuality(
        sessionId,
        latencyMs,
        missedHeartbeats,
        connectionType
      );
      
      // Update local state
      this.updateState({ connectionQuality: response.quality as any });
      
      // If reconnect recommended, trigger reconnect
      if (response.reconnectRecommended && this.state.isConnected) {
        console.warn('Server recommends reconnection due to poor connection quality');
        this.reconnect();
      }
    } catch (error) {
      console.error('Failed to update connection quality:', error);
    }
  }
  
  // State management
  private updateState(updates: Partial<ConnectionState>): void {
    const prevState = { ...this.state };
    this.state = { ...this.state, ...updates };
    
    // Emit state change event
    this.emit('state_change', { 
      previous: prevState, 
      current: this.state 
    });
  }
  
  public getState(): ConnectionState {
    return { ...this.state };
  }
  
  // Public API for simulator control
  public async startSimulator(): Promise<boolean> {
    const sessionId = this.state.sessionId;
    if (!sessionId) return false;
    
    try {
      // This would call your simulator start API
      // For now, we'll just update the state
      this.updateState({ 
        simulatorStatus: 'STARTING' 
      });
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      this.updateState({ 
        simulatorId: `sim-${Date.now()}`,
        simulatorStatus: 'RUNNING' 
      });
      
      return true;
    } catch (error) {
      console.error('Failed to start simulator:', error);
      this.updateState({ 
        error: error instanceof Error ? error.message : 'Failed to start simulator' 
      });
      return false;
    }
  }
  
  public async stopSimulator(): Promise<boolean> {
    const simulatorId = this.state.simulatorId;
    if (!simulatorId) return false;
    
    try {
      // This would call your simulator stop API
      // For now, we'll just update the state
      this.updateState({ 
        simulatorStatus: 'STOPPING' 
      });
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      this.updateState({ 
        simulatorStatus: 'STOPPED',
        simulatorId: null
      });
      
      return true;
    } catch (error) {
      console.error('Failed to stop simulator:', error);
      this.updateState({ 
        error: error instanceof Error ? error.message : 'Failed to stop simulator' 
      });
      return false;
    }
  }
  
  // Order management
  public async submitOrder(order: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price?: number;
    type: 'MARKET' | 'LIMIT';
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
    const sessionId = this.state.sessionId;
    if (!sessionId) {
      return { success: false, error: 'No active session' };
    }
    
    if (this.state.connectionQuality === 'poor') {
      return { success: false, error: 'Connection quality too poor for order submission' };
    }
    
    try {
      const response = await this.ordersApi.submitOrder({
        sessionId,
        symbol: order.symbol,
        side: order.side,
        quantity: order.quantity,
        price: order.price,
        type: order.type,
        requestId: `order-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`
      });
      
      return { 
        success: response.success, 
        orderId: response.orderId,
        error: response.errorMessage
      };
    } catch (error) {
      console.error('Order submission error:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Order submission failed' 
      };
    }
  }
  
  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
    const sessionId = this.state.sessionId;
    if (!sessionId) {
      return { success: false, error: 'No active session' };
    }
    
    try {
      const response = await this.ordersApi.cancelOrder(sessionId, orderId);
      
      return { 
        success: response.success,
        error: response.success ? undefined : 'Failed to cancel order'
      };
    } catch (error) {
      console.error('Order cancellation error:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Order cancellation failed' 
      };
    }
  }
}