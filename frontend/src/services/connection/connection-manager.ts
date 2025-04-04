// src/services/connection/connection-manager.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/ws-manager';
import { ExchangeDataStream, MarketData, OrderUpdate, PortfolioUpdate } from '../sse/exchange-data-stream';
import { SessionApi } from '../../api/session';
import { OrdersApi } from '../../api/order';
import { HttpClient } from '../../api/http-client';
import { SessionManager } from '../session/session-manager';
import { config } from '../../config';

import { RecoveryManager } from './recovery-manager';

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
  private sseManager: ExchangeDataStream;
  private recoveryManager: RecoveryManager;
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
      
    // Create Recovery Manager with TokenManager
    this.recoveryManager = new RecoveryManager(this, tokenManager);
    
    // Forward recovery events
    this.recoveryManager.on('recovery_attempt', (data: any) => {
      this.emit('recovery_attempt', data);
    });
    
    this.recoveryManager.on('recovery_success', (data: any) => {
      this.emit('recovery_success', data);
    });
    
    this.recoveryManager.on('recovery_failed', (data: any) => {
      this.emit('recovery_failed', data);
    });
    
    this.recoveryManager.on('network_offline', () => {
      this.emit('network_offline');
    });
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
    this.sessionApi = new SessionApi(this.httpClient, this.tokenManager);
    this.ordersApi = new OrdersApi(this.httpClient);
    
    // Create WebSocket manager
    this.wsManager = new WebSocketManager(tokenManager, {
      heartbeatInterval: 15000,
      reconnectMaxAttempts: 15,
      circuitBreakerThreshold: 5,
      circuitBreakerResetTimeMs: 60000
    });
    
    // Create Market Data stream and store as sseManager
    this.sseManager = new ExchangeDataStream(tokenManager, {
      reconnectMaxAttempts: 15
    });
    
    // Set up event listeners
    this.setupEventListeners();
  }
  
  // Add this method for manual recovery trigger
  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    return this.recoveryManager.attemptRecovery(reason);
  }

  private setupEventListeners(): void {
    // WebSocket event listeners
    this.wsManager.on('connected', () => {
      this.updateState({ isConnected: true, error: null });
      this.emit('connected', { connected: true });
      //this.startHeartbeat();
      //this.startKeepAlive();
    });
    
    this.wsManager.on('disconnected', () => {
      this.updateState({ isConnected: false });
      this.emit('disconnected');
      //this.stopHeartbeat();
      //this.stopKeepAlive();
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
    this.sseManager.on('market-data-updated', (data: Record<string, MarketData>) => {
      this.marketData = data;
      this.emit('market_data', data);
    });
    
    this.sseManager.on('orders-updated', (data: Record<string, OrderUpdate>) => {
      this.orders = data;
      this.emit('orders', data);
    });
    
    this.sseManager.on('portfolio-updated', (data: PortfolioUpdate) => {
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
  public updateRecoveryAuthState(isAuthenticated: boolean): void {
    // If recoveryManager exists, call its method
    if (this.recoveryManager) {
      this.recoveryManager.updateAuthState(isAuthenticated);
    }
  }
  
  public async connect(): Promise<boolean> {
    console.log('Attempting to connect and create session...');
    
    // Check if we have a valid token first
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      console.warn('Cannot connect - user is not authenticated');
      this.updateState({ 
        error: 'Authentication required before connecting',
        isConnected: false,
        isConnecting: false
      });
      return false;
    }
    
    if (this.state.isConnected || this.state.isConnecting) {
      return this.state.isConnected;
    }
    
    this.updateState({ isConnecting: true, error: null });
    
    try {
      // Step 1: Get or create session
      let sessionId = SessionManager.getSessionId();
      
      if (!sessionId) {
        console.log('No existing session found, creating new session...');
  
        // Create a new session
        const response = await this.sessionApi.createSession();
        
        console.log('Session creation response:', {
          success: response.success,
          sessionId: response.sessionId,
          errorMessage: response.errorMessage
        });
        
        if (!response.success) {
          throw new Error(response.errorMessage || 'Failed to create session');
        }
        
        sessionId = response.sessionId;
        SessionManager.setSessionId(sessionId);
      }
      
      this.updateState({ sessionId });
      
      // Step 2: Check session readiness
      console.log('Checking session readiness...');
      const isReady = await this.checkSessionReadiness(sessionId);
      if (!isReady) {
        throw new Error('Session failed readiness check');
      }
      
      // Step 3: Connect WebSocket
      console.log('Establishing WebSocket connection...');
      const wsConnected = await this.wsManager.connect(sessionId);
      
      if (!wsConnected) {
        throw new Error('Failed to establish WebSocket connection');
      }
      
      console.log('WebSocket connection established successfully');
      
      // Step 4: Get session state to determine if simulator is already running
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
      
      // Start heartbeat for WebSocket
      this.startHeartbeat();
      
      // Step 5: Connect to market data stream after WebSocket is connected
      console.log('Establishing market data stream...');
      await this.sseManager.connect(sessionId);
        
      // Add this at the end of the method:
      if (this.state.isConnected) {
        // After successful connection, update timestamp in session storage
        // to coordinate with other tabs
        SessionManager.updateActivity();
      }
      
      return true;
    } catch (error) {
      console.error('Full session creation error:', error);
  
      if (error instanceof Error) {
        console.error('Error name:', error.name);
        console.error('Error message:', error.message);
        
        // If it's a network error, log additional details
        if (error.name === 'TypeError') {
          console.error('Potential network or CORS issue detected');
        }
      }
  
      this.updateState({ 
        isConnecting: false, 
        error: error instanceof Error ? error.message : 'Connection failed' 
      });
      return false;
    }
  }

  // Add cleanup for recovery manager
  public dispose(): void {
    this.disconnect();
    this.recoveryManager.dispose();
  }

  // Add a new method to check session readiness
  private async checkSessionReadiness(sessionId: string): Promise<boolean> {
    const maxAttempts = 5;
    const retryDelay = 1000; // 1 second
    
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        const ready = await this.sessionApi.checkSessionReady(sessionId);
        
        if (ready.success) {
          console.log('Session is ready');
          return true;
        }
        
        console.log(`Session not ready yet (attempt ${attempt}/${maxAttempts}): ${ready.status}`);
        
        if (attempt < maxAttempts) {
          // Wait before trying again
          await new Promise(resolve => setTimeout(resolve, retryDelay));
        }
      } catch (error) {
        console.error(`Error checking session readiness (attempt ${attempt}/${maxAttempts}):`, error);
        
        if (attempt < maxAttempts) {
          // Wait before trying again
          await new Promise(resolve => setTimeout(resolve, retryDelay));
        }
      }
    }
    
    return false;
  }
  
  public disconnect(): void {
    // Disconnect WebSocket
    this.wsManager.disconnect();
    
    // Disconnect market data stream
    this.sseManager.disconnect();
    
    // Stop heartbeat timer
    this.stopHeartbeat();
    
    // Clear session store
    SessionManager.clearSession();
    
    // Reset state
    this.updateState({
      isConnected: false,
      isConnecting: false,
      sessionId: null,
      simulatorId: null,
      simulatorStatus: 'UNKNOWN',
      error: null
    });
    
    // Clean up recovery manager
    this.recoveryManager.dispose();
  }
  
  public async reconnect(): Promise<boolean> {
    // Check if we have a session ID
    const sessionId = this.state.sessionId || SessionManager.getSessionId();
    if (!sessionId) {
      return this.connect();
    }
    
    this.updateState({ isConnecting: true, error: null });
    
    try {
      const attempts = SessionManager.incrementReconnectAttempts();
      
      // Try to reconnect session
      const response = await this.sessionApi.reconnectSession(sessionId, attempts);
      
      if (!response.success) {
        throw new Error(response.errorMessage || 'Failed to reconnect session');
      }
      
      // Disconnect existing connections
      this.wsManager.disconnect();
      this.sseManager.disconnect();
      //this.stopHeartbeat();
      //this.stopKeepAlive();
      
      // Connect WebSocket
      const wsConnected = await this.wsManager.connect(response.sessionId);

      if (!wsConnected) {
        throw new Error('Failed to establish WebSocket connection');
      }
      
      // Connect to market data stream
      await this.sseManager.connect(response.sessionId);
      
      // Update state
      this.updateState({
        isConnected: true,
        isConnecting: false,
        sessionId: response.sessionId,
        error: null
      });
      
      // Store in session storage
      SessionManager.saveSession({
        sessionId: response.sessionId,
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
    console.group('🚀 Streaming Market Data');
    console.log('Symbols:', symbols);
    
    if (!this.state.sessionId || !this.state.isConnected) {
      console.error('Cannot stream - No active session');
      console.groupEnd();
      return false;
    }
      
    console.log('ConnectionManager - Streaming market data, session ID:', this.state.sessionId);
    console.log('ConnectionManager - Symbols:', symbols);

    const result = await this.sseManager.connect(
      this.state.sessionId, 
      { symbols: symbols.join(',') } as any
    );

    console.log('Stream Connection Result:', result);
    console.groupEnd();
    
    return result;
  }
  
  // Control simulator
  public async startSimulator(): Promise<boolean> {
    if (!this.state.isConnected) {
      console.warn('Cannot start simulator - not connected');
      return false;
    }
    
    try {
      this.updateState({ simulatorStatus: 'STARTING' });
      
      // Just make the request - token is handled by HttpClient
      const response = await this.httpClient.post<{success: boolean}>('/simulators');
      
      if (response.success) {
        this.updateState({
          simulatorStatus: 'RUNNING'
        });
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Failed to start simulator:', error);
      this.updateState({ simulatorStatus: 'ERROR' });
      return false;
    }
  }

  public async stopSimulator(): Promise<boolean> {
    if (!this.state.isConnected) {
      console.warn('Cannot stop simulator - not connected');
      return false;
    }
    
    try {
      this.updateState({ simulatorStatus: 'STOPPING' });
      
      // Just make the request - no IDs needed
      const response = await this.httpClient.delete<{success: boolean}>('/simulators');
      
      if (response.success) {
        this.updateState({
          simulatorStatus: 'STOPPED'
        });
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Failed to stop simulator:', error);
      return false;
    }
  }

  public async getSimulatorStatus(): Promise<string> {
    try {
      const response = await this.httpClient.get<{success: boolean, status: string}>('/simulators');
      
      if (response.success) {
        // Update local state
        this.updateState({ simulatorStatus: response.status });
        return response.status;
      }
      
      return 'UNKNOWN';
    } catch (error) {
      console.error('Failed to get simulator status:', error);
      return 'ERROR';
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