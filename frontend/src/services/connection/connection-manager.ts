// src/services/connection/connection-manager.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/ws-manager';
import { MarketDataStream, MarketData, OrderUpdate, PortfolioUpdate } from '../sse/market-data-stream';
import { SessionApi } from '../../api/session';
import { OrdersApi } from '../../api/order';
import { HttpClient } from '../../api/http-client';
import { SessionStore } from '../session/session-store';
import { config } from '../../config';


export type ConnectionQuality = 'good' | 'degraded' | 'poor';

export interface ConnectionState {
  isConnected: boolean;
  isConnecting: boolean;
  sessionId: string | null;
  connectionQuality: ConnectionQuality;
  lastHeartbeatTime: number;
  heartbeatLatency: number | null;
  missedHeartbeats: number;
  error: string | null;
  circuitBreakerState: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
  simulatorId: string | null;
  simulatorStatus: string;
}

export class ConnectionManager extends EventEmitter {
  private state: ConnectionState;
  private tokenManager: TokenManager;
  private wsManager: WebSocketManager;
  private marketDataStream: MarketDataStream;
  private sessionApi: SessionApi;
  private ordersApi: OrdersApi;
  private httpClient: HttpClient;
  
  // Timers
  private heartbeatInterval: number | null = null;
  private keepAliveInterval: number | null = null;
  
  // Data caches
  private marketData: Record<string, MarketData> = {};
  private orders: Record<string, OrderUpdate> = {};
  private portfolio: PortfolioUpdate | null = null;
  
  constructor(
    tokenManager: TokenManager
  ) {
    super();
    
    this.tokenManager = tokenManager;
    
    // Initialize state
    this.state = {
      isConnected: false,
      isConnecting: false,
      sessionId: null,
      connectionQuality: 'good',
      lastHeartbeatTime: 0,
      heartbeatLatency: null,
      missedHeartbeats: 0,
      error: null,
      circuitBreakerState: 'CLOSED',
      simulatorId: null,
      simulatorStatus: 'UNKNOWN'
    };
    
    // Create HTTP client
    this.httpClient = new HttpClient(tokenManager);
    
    // Create API clients
    this.sessionApi = new SessionApi(this.httpClient);
    this.ordersApi = new OrdersApi(this.httpClient);
    
    // Create WebSocket manager
    this.wsManager = new WebSocketManager(tokenManager, {
      heartbeatInterval: 15000,
      reconnectMaxAttempts: 15,
      circuitBreakerThreshold: 5,
      circuitBreakerResetTimeMs: 60000
    });
    
    // Create Market Data stream
    this.marketDataStream = new MarketDataStream(tokenManager, {
      reconnectMaxAttempts: 15
    });
    
    // Set up event listeners
    this.setupEventListeners();
  }
  
  private setupEventListeners(): void {
    // WebSocket event listeners
    this.wsManager.on('connected', () => {
      this.updateState({ isConnected: true, error: null });
      this.emit('connected', { connected: true });
      this.startHeartbeat();
      this.startKeepAlive();
    });
    
    this.wsManager.on('disconnected', () => {
      this.updateState({ isConnected: false });
      this.emit('disconnected');
      this.stopHeartbeat();
      this.stopKeepAlive();
    });
    
    this.wsManager.on('reconnecting', (data: any) => {
      this.updateState({ isConnecting: true });
      this.emit('reconnecting', data);
    });
    
    this.wsManager.on('heartbeat', (data: any) => {
      this.handleHeartbeat(data);
    });
    
    this.wsManager.on('error', (data: any) => {
      this.updateState({ error: data.error?.message || 'Connection error' });
      this.emit('error', data);
    });
    
    // Circuit breaker events
    this.wsManager.on('circuit_trip', () => {
      this.updateState({ circuitBreakerState: 'OPEN' });
    });
    
    this.wsManager.on('circuit_half_open', () => {
      this.updateState({ circuitBreakerState: 'HALF_OPEN' });
    });
    
    this.wsManager.on('circuit_closed', () => {
      this.updateState({ circuitBreakerState: 'CLOSED' });
    });
    
    // Market data stream listeners
    this.marketDataStream.on('market-data-updated', (data: Record<string, MarketData>) => {
      this.marketData = data;
      this.emit('market_data', data);
    });
    
    this.marketDataStream.on('orders-updated', (data: Record<string, OrderUpdate>) => {
      this.orders = data;
      this.emit('orders', data);
    });
    
    this.marketDataStream.on('portfolio-updated', (data: PortfolioUpdate) => {
      this.portfolio = data;
      this.emit('portfolio', data);
    });
    
    // Additional message handlers
    this.wsManager.on('simulator_update', (data: any) => {
      this.updateState({ 
        simulatorStatus: data.status,
        simulatorId: data.simulatorId || this.state.simulatorId
      });
      this.emit('simulator_update', data);
    });
  }
  
  // Connect all necessary connections for a session
  public async connect(): Promise<boolean> {
    if (this.state.isConnected || this.state.isConnecting) {
      return this.state.isConnected;
    }
    
    this.updateState({ isConnecting: true, error: null });
    
    try {
      // Check if we have a stored session
      let sessionId = SessionStore.getSessionId();
      
      if (!sessionId) {
        // Create a new session
        const response = await this.sessionApi.createSession();
        
        if (!response.success) {
          throw new Error(response.errorMessage || 'Failed to create session');
        }
        
        sessionId = response.sessionId;
        SessionStore.setSessionId(sessionId);
      }
      
      this.updateState({ sessionId });
      
      // Connect WebSocket
      const wsConnected = await this.wsManager.connect(sessionId);
      
      if (!wsConnected) {
        throw new Error('Failed to establish WebSocket connection');
      }
      
      // Connect to market data stream
      await this.marketDataStream.connect(sessionId);
      
      // Get session state to determine if simulator is already running
      const sessionState = await this.sessionApi.getSessionState(sessionId);
      
      // Update state with simulator info
      if (sessionState.success) {
        this.updateState({
          simulatorId: sessionState.simulatorId,
          simulatorStatus: sessionState.simulatorStatus || 'UNKNOWN'
        });
      }
      
      this.updateState({ 
        isConnected: true, 
        isConnecting: false 
      });
      
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
    // Disconnect WebSocket
    this.wsManager.disconnect();
    
    // Disconnect market data stream
    this.marketDataStream.disconnect();
    
    // Stop timers
    this.stopHeartbeat();
    this.stopKeepAlive();
    
    // Clear session store
    SessionStore.clearSession();
    
    // Reset state
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
    // Check if we have a session ID
    const sessionId = this.state.sessionId || SessionStore.getSessionId();
    if (!sessionId) {
      return this.connect();
    }
    
    this.updateState({ isConnecting: true, error: null });
    
    try {
      const attempts = SessionStore.incrementReconnectAttempts();
      
      // Try to reconnect session
      const response = await this.sessionApi.reconnectSession(sessionId, attempts);
      
      if (!response.success) {
        throw new Error(response.errorMessage || 'Failed to reconnect session');
      }
      
      // Disconnect existing connections
      this.wsManager.disconnect();
      this.marketDataStream.disconnect();
      this.stopHeartbeat();
      this.stopKeepAlive();
      
      // Connect WebSocket
      const wsConnected = await this.wsManager.connect(response.sessionId);

      if (!wsConnected) {
        throw new Error('Failed to establish WebSocket connection');
      }
      
      // Connect to market data stream
      await this.marketDataStream.connect(response.sessionId);
      
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
  
  // Handle heartbeat data from websocket
  private handleHeartbeat(data: any): void {
    const now = Date.now();
    const latency = data.latency || (now - this.state.lastHeartbeatTime);
    
    this.updateState({
      lastHeartbeatTime: now,
      heartbeatLatency: latency,
      missedHeartbeats: 0
    });
    
    // Update connection quality based on latency
    let quality: ConnectionQuality = 'good';
    if (latency > 500) {
      quality = 'degraded';
    } else if (latency > 1000) {
      quality = 'poor';
    }
    
    this.updateState({ connectionQuality: quality });
    
    this.emit('heartbeat', {
      timestamp: now,
      latency
    });
  }
  
  // Start heartbeat for websocket connection
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatInterval = window.setInterval(() => {
      if (!this.state.isConnected) return;
      
      // Send heartbeat via WebSocket
      this.wsManager.send({ 
        type: 'heartbeat', 
        timestamp: Date.now() 
      });
    }, 15000); // Every 15 seconds
  }
  
  private stopHeartbeat(): void {
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
  
  // Start keep-alive for REST API connection
  private startKeepAlive(): void {
    this.stopKeepAlive();
    
    this.keepAliveInterval = window.setInterval(async () => {
      if (!this.state.isConnected || !this.state.sessionId) return;
      
      try {
        // Send keep-alive to server
        await this.sessionApi.keepAlive(this.state.sessionId);
        
        // Update session store
        SessionStore.updateActivity();
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
  
  private updateState(updates: Partial<ConnectionState>): void {
    const prevState = { ...this.state };
    this.state = { ...this.state, ...updates };
    
    // Emit state change event
    this.emit('state_change', {
      previous: prevState,
      current: this.state
    });
  }
  
  // Get current connection state
  public getState(): ConnectionState {
    return { ...this.state };
  }
  
  // Stream market data for specific symbols
  public async streamMarketData(symbols: string[] = []): Promise<boolean> {
    if (!this.state.sessionId || !this.state.isConnected) {
      return false;
    }
    
    // Use type assertion to avoid TypeScript error
    return this.marketDataStream.connect(
      this.state.sessionId, 
      { symbols: symbols.join(',') } as any
    );
  }
  
  // Control simulator
  public async startSimulator(): Promise<boolean> {
    if (!this.state.sessionId) {
      return false;
    }
    
    try {
      this.updateState({ simulatorStatus: 'STARTING' });
      
      // Add type assertion for response
      const response = await this.httpClient.post('/api/simulator/start', {
        sessionId: this.state.sessionId
      }) as { success: boolean; simulatorId: string };
      
      if (response.success) {
        this.updateState({
          simulatorId: response.simulatorId,
          simulatorStatus: 'RUNNING'
        });
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Failed to start simulator:', error);
      return false;
    }
  }
  
  public async stopSimulator(): Promise<boolean> {
    if (!this.state.sessionId || !this.state.simulatorId) {
      return false;
    }
    
    try {
      this.updateState({ simulatorStatus: 'STOPPING' });
      
      const response = await this.httpClient.post('/api/simulator/stop', {
        sessionId: this.state.sessionId,
        simulatorId: this.state.simulatorId
      }) as { success: boolean };
      
      if (response.success) {
        this.updateState({
          simulatorStatus: 'STOPPED',
          simulatorId: null
        });
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Failed to stop simulator:', error);
      return false;
    }
  }
  
  // Submit order
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
  
  // Cancel order
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
  
  // Get market data
  public getMarketData(): Record<string, MarketData> {
    return { ...this.marketData };
  }
  
  // Get orders
  public getOrders(): Record<string, OrderUpdate> {
    return { ...this.orders };
  }
  
  // Get portfolio
  public getPortfolio(): PortfolioUpdate | null {
    return this.portfolio ? { ...this.portfolio } : null;
  }
}