// src/services/connection/ConnectionManager.ts

import { TokenManager } from '../auth/token-manager';
import { BackoffStrategy } from '../utils/backoff-strategy';
import { CircuitBreaker, CircuitState } from '../utils/circuit-breaker';
import { EventEmitter } from '../utils/event-emitter';
import { HttpClient } from '../api/http-client';

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
  restCircuitState: CircuitState;
  wsCircuitState: CircuitState;
  sseCircuitState: CircuitState;
  simulatorId: string | null;
  simulatorStatus: string;
}

export class ConnectionManager extends EventEmitter {
  private state: ConnectionState;
  private tokenManager: TokenManager;
  private httpClient: HttpClient;
  private ws: WebSocket | null = null;
  private sseSource: EventSource | null = null;
  
  // Circuit breakers for each connection type
  private restCircuitBreaker: CircuitBreaker;
  private wsCircuitBreaker: CircuitBreaker;
  private sseCircuitBreaker: CircuitBreaker;
  
  // Timers
  private heartbeatInterval: number | null = null;
  private stateMonitorInterval: number | null = null;
  private reconnectTimer: number | null = null;
  
  private marketData: Record<string, any> = {};
  private orders: Record<string, any> = {};
  private portfolio: any = null;
  
  constructor(
    restApiUrl: string,
    websocketUrl: string,
    sseUrl: string,
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
      restCircuitState: CircuitState.CLOSED,
      wsCircuitState: CircuitState.CLOSED,
      sseCircuitState: CircuitState.CLOSED,
      simulatorId: null,
      simulatorStatus: 'UNKNOWN'
    };
    
    // Create circuit breakers
    this.restCircuitBreaker = new CircuitBreaker('rest-api', 5, 60000);
    this.wsCircuitBreaker = new CircuitBreaker('websocket', 5, 60000);
    this.sseCircuitBreaker = new CircuitBreaker('sse', 5, 60000);
    
    // Initialize HTTP client
    this.httpClient = new HttpClient(restApiUrl, tokenManager);
    
    // Register circuit breaker state change listeners
    this.restCircuitBreaker.onStateChange((state, prevState) => 
      this.handleCircuitStateChange('rest', state, prevState));
    this.wsCircuitBreaker.onStateChange((state, prevState) => 
      this.handleCircuitStateChange('websocket', state, prevState));
    this.sseCircuitBreaker.onStateChange((state, prevState) => 
      this.handleCircuitStateChange('sse', state, prevState));
      
    // Store URLs for connections
    this.websocketUrl = websocketUrl;
    this.sseUrl = sseUrl;
  }
  
  // Connect all necessary connections for a session
  public async connect(): Promise<boolean> {
    if (this.state.isConnected || this.state.isConnecting) {
      return this.state.isConnected;
    }
    
    this.updateState({ isConnecting: true });
    
    try {
      // First, try to create or resume a session via REST
      const sessionId = await this.restCircuitBreaker.execute(async () => {
        const response = await this.httpClient.post<{success: boolean, sessionId: string}>(
          '/api/session/create', {});
        
        if (!response.success) {
          throw new Error('Failed to create session');
        }
        
        return response.sessionId;
      });
      
      this.updateState({ sessionId });
      
      // Now connect WebSocket
      const wsConnected = await this.connectWebSocket(sessionId);
      
      if (!wsConnected) {
        throw new Error('Failed to establish WebSocket connection');
      }
      
      // Get session state to determine if simulator is already running
      const sessionState = await this.restCircuitBreaker.execute(async () => {
        const response = await this.httpClient.get(
          `/api/session/state?sessionId=${sessionId}`);
        return response;
      });
      
      // Update state with simulator info
      if (sessionState.success) {
        this.updateState({
          simulatorId: sessionState.simulatorId,
          simulatorStatus: sessionState.simulatorStatus || 'UNKNOWN'
        });
      }
      
      // Start heartbeat
      this.startHeartbeat();
      
      // Start state monitoring
      this.startStateMonitoring();
      
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
    // Stop monitoring
    this.stopHeartbeat();
    this.stopStateMonitoring();
    
    // Disconnect WebSocket
    if (this.ws) {
      this.ws.close(1000, 'Client disconnecting');
      this.ws = null;
    }
    
    // Close SSE connection
    if (this.sseSource) {
      this.sseSource.close();
      this.sseSource = null;
    }
    
    // Clear reconnect timer
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
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
  
  private async connectWebSocket(sessionId: string): Promise<boolean> {
    return new Promise((resolve) => {
      try {
        // Close existing connection if any
        if (this.ws) {
          this.ws.close();
          this.ws = null;
        }
        
        // Get auth token
        this.tokenManager.getAccessToken().then(token => {
          if (!token) {
            resolve(false);
            return;
          }
          
          // Create WebSocket with session ID and token
          const url = `${this.websocketUrl}?sessionId=${sessionId}&token=${token}`;
          this.ws = new WebSocket(url);
          
          // Set up event handlers
          this.ws.onopen = () => {
            this.setupWebSocketHandlers();
            resolve(true);
          };
          
          this.ws.onerror = (error) => {
            console.error('WebSocket connection error:', error);
            resolve(false);
          };
          
          // Set connection timeout
          const connectionTimeout = setTimeout(() => {
            if (this.ws && this.ws.readyState !== WebSocket.OPEN) {
              console.error('WebSocket connection timeout');
              this.ws.close();
              this.ws = null;
              resolve(false);
            }
          }, 10000); // 10 second timeout
          
          // Clear timeout when connection opens
          this.ws.addEventListener('open', () => {
            clearTimeout(connectionTimeout);
          });
        });
      } catch (error) {
        console.error('Error connecting WebSocket:', error);
        resolve(false);
      }
    });
  }
  
  private setupWebSocketHandlers() {
    if (!this.ws) return;
    
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const msgType = data.type;
        
        if (msgType === 'heartbeat_ack') {
          this.handleHeartbeat(data);
        } else if (msgType === 'connection_quality_update') {
          this.updateState({ connectionQuality: data.quality });
          this.emit('connection_quality_changed', {
            previous: this.state.connectionQuality,
            current: data.quality
          });
        } else if (msgType === 'simulator_update') {
          this.updateState({ 
            simulatorStatus: data.status,
            simulatorId: data.simulatorId || this.state.simulatorId
          });
          this.emit('simulator_update', data);
        } else {
          // Handle other message types
          this.emit(msgType, data);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };
    
    this.ws.onclose = (event) => {
      console.log(`WebSocket closed: ${event.code} ${event.reason}`);
      this.ws = null;
      
      // Update connection state
      if (this.state.isConnected) {
        this.updateState({ isConnected: false });
        this.emit('disconnected');
        
        // Try to reconnect if not deliberate close
        if (event.code !== 1000) {
          this.attemptReconnect();
        }
      }
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.emit('error', { type: 'websocket_error', error });
    };
  }
  
  private startSSE(sessionId: string, symbols: string[] = []): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      this.tokenManager.getAccessToken().then(token => {
        if (!token) {
          resolve(false);
          return;
        }
        
        // Close existing SSE if any
        if (this.sseSource) {
          this.sseSource.close();
          this.sseSource = null;
        }
        
        // Build URL with parameters
        let url = `${this.sseUrl}?sessionId=${sessionId}&token=${token}`;
        if (symbols.length > 0) {
          url += `&symbols=${symbols.join(',')}`;
        }
        
        // Create EventSource
        this.sseSource = new EventSource(url);
        
        // Set up event handlers
        this.sseSource.onopen = () => {
          console.log('SSE connection opened');
          resolve(true);
        };
        
        this.sseSource.onerror = (error) => {
          console.error('SSE connection error:', error);
          if (this.sseSource?.readyState === EventSource.CLOSED) {
            this.sseSource = null;
          }
          resolve(false);
        };
        
        // Listen for specific event types
        this.sseSource.addEventListener('market-data', (event) => {
          try {
            const data = JSON.parse(event.data);
            
            // Update market data cache
            if (data.marketData) {
              data.marketData.forEach((item: any) => {
                if (item.symbol) {
                  this.marketData[item.symbol] = item;
                }
              });
              
              this.emit('market_data', this.marketData);
            }
            
            // Update order cache
            if (data.orderUpdates) {
              data.orderUpdates.forEach((update: any) => {
                if (update.orderId) {
                  this.orders[update.orderId] = update;
                }
              });
              
              this.emit('orders', this.orders);
            }
            
            // Update portfolio
            if (data.portfolio) {
              this.portfolio = data.portfolio;
              this.emit('portfolio', this.portfolio);
            }
          } catch (error) {
            console.error('Error parsing SSE data:', error);
          }
        });
        
        // Set connection timeout
        const connectionTimeout = setTimeout(() => {
          if (this.sseSource && this.sseSource.readyState !== EventSource.OPEN) {
            console.error('SSE connection timeout');
            this.sseSource.close();
            this.sseSource = null;
            resolve(false);
          }
        }, 10000); // 10 second timeout
        
        // Cancel timeout when connection opens
        this.sseSource.addEventListener('open', () => {
          clearTimeout(connectionTimeout);
        });
      });
    });
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
  
  // Start heartbeat for all connection types
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatInterval = window.setInterval(() => {
      if (!this.state.isConnected || !this.state.sessionId) return;
      
      // Send heartbeat via WebSocket
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ 
          type: 'heartbeat', 
          timestamp: Date.now() 
        }));
      }
      
      // Also send keep-alive to REST API
      this.httpClient.post('/api/session/keep-alive', {
        sessionId: this.state.sessionId
      }).catch(err => console.error('Keep-alive error:', err));
      
    }, 15000); // Every 15 seconds
  }
  
  private stopHeartbeat(): void {
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
  
  // Monitor all connection states
  private startStateMonitoring(): void {
    this.stopStateMonitoring();
    
    this.stateMonitorInterval = window.setInterval(() => {
      if (!this.state.isConnected) return;
      
      const now = Date.now();
      const timeSinceHeartbeat = now - this.state.lastHeartbeatTime;
      
      // Check for missed heartbeats
      if (timeSinceHeartbeat > 30000) { // No heartbeat for 30s
        const missedHeartbeats = Math.floor(timeSinceHeartbeat / 15000);
        this.updateState({ missedHeartbeats });
        
        // Update connection quality based on missed heartbeats
        let quality: ConnectionQuality = this.state.connectionQuality;
        if (missedHeartbeats >= 3) {
          quality = 'poor';
        } else if (missedHeartbeats > 0) {
          quality = 'degraded';
        }
        
        this.updateState({ connectionQuality: quality });
        
        // If too many missed heartbeats, attempt reconnect
        if (missedHeartbeats >= 5) {
          console.warn('Too many missed heartbeats, attempting reconnect');
          this.reconnect();
        }
      }
    }, 5000); // Check every 5 seconds
  }
  
  private stopStateMonitoring(): void {
    if (this.stateMonitorInterval !== null) {
      clearInterval(this.stateMonitorInterval);
      this.stateMonitorInterval = null;
    }
  }
  
  private attemptReconnect(): void {
    if (this.reconnectTimer !== null) {
      return; // Already attempting to reconnect
    }
    
    // Use backoff strategy for reconnect delay
    const backoff = new BackoffStrategy(1000, 30000);
    const delay = backoff.nextBackoffTime();
    
    console.log(`Attempting reconnect in ${delay}ms...`);
    
    this.reconnectTimer = window.setTimeout(async () => {
      this.reconnectTimer = null;
      
      // Try to reconnect
      const success = await this.reconnect();
      
      if (!success) {
        // If reconnect failed, try again with backoff
        this.attemptReconnect();
      }
    }, delay);
  }
  
  public async reconnect(): Promise<boolean> {
    // Disconnect current connections without resetting session ID
    const sessionId = this.state.sessionId;
    if (!sessionId) {
      return this.connect();
    }
    
    // Close current connections
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    
    if (this.sseSource) {
      this.sseSource.close();
      this.sseSource = null;
    }
    
    this.stopHeartbeat();
    this.stopStateMonitoring();
    
    this.updateState({ isConnecting: true });
    
    try {
      // Attempt to reconnect via REST API
      const reconnectResult = await this.restCircuitBreaker.execute(async () => {
        const response = await this.httpClient.post(
          `/api/session/reconnect`, {
            sessionId,
            reconnectAttempt: 1
          });
        return response;
      });
      
      if (!reconnectResult.success) {
        throw new Error(reconnectResult.error || 'Reconnection failed');
      }
      
      // Reconnect WebSocket
      const wsConnected = await this.connectWebSocket(reconnectResult.sessionId);
      
      if (!wsConnected) {
        throw new Error('Failed to reestablish WebSocket connection');
      }
      
      // Update state with new session info
      this.updateState({
        sessionId: reconnectResult.sessionId,
        simulatorId: reconnectResult.simulatorId,
        simulatorStatus: reconnectResult.simulatorStatus || 'UNKNOWN',
        isConnected: true,
        isConnecting: false,
        error: null
      });
      
      // Restart heartbeat and monitoring
      this.startHeartbeat();
      this.startStateMonitoring();
      
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
  
  private updateState(updates: Partial<ConnectionState>): void {
    const prevState = { ...this.state };
    this.state = { ...this.state, ...updates };
    
    // Emit state change event
    this.emit('state_change', {
      previous: prevState,
      current: this.state
    });
    
    // Emit specific state changes
    if (prevState.isConnected !== this.state.isConnected) {
      this.emit(this.state.isConnected ? 'connected' : 'disconnected');
    }
    
    if (prevState.connectionQuality !== this.state.connectionQuality) {
      this.emit('connection_quality_changed', {
        previous: prevState.connectionQuality,
        current: this.state.connectionQuality
      });
    }
  }
  
  private handleCircuitStateChange(
    circuitType: string, 
    newState: CircuitState, 
    prevState: CircuitState
  ): void {
    // Update the appropriate circuit state in our state object
    if (circuitType === 'rest') {
      this.updateState({ restCircuitState: newState });
    } else if (circuitType === 'websocket') {
      this.updateState({ wsCircuitState: newState });
    } else if (circuitType === 'sse') {
      this.updateState({ sseCircuitState: newState });
    }
    
    // Emit circuit state change event
    this.emit('circuit_state_change', {
      type: circuitType,
      previous: prevState,
      current: newState
    });
    
    // If circuit is reset from open to closed, we could retry operations
    if (prevState === CircuitState.OPEN && newState === CircuitState.CLOSED) {
      this.emit('circuit_reset', { type: circuitType });
    }
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
    
    try {
      return await this.startSSE(this.state.sessionId, symbols);
    } catch (error) {
      console.error('Failed to start market data stream:', error);
      return false;
    }
  }
  
  // Send a message via WebSocket
  public send(message: any): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false;
    }
    
    try {
      this.ws.send(typeof message === 'string' ? message : JSON.stringify(message));
      return true;
    } catch (error) {
      console.error('Error sending WebSocket message:', error);
      return false;
    }
  }
  
  // Control simulator
  public async startSimulator(): Promise<boolean> {
    if (!this.state.sessionId) {
      return false;
    }
    
    try {
      const response = await this.httpClient.post('/api/simulator', {
        sessionId: this.state.sessionId
      });
      
      if (response.success) {
        this.updateState({
          simulatorId: response.simulatorId,
          simulatorStatus: 'STARTING'
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
      const response = await this.httpClient.delete(`/api/simulator/${this.state.simulatorId}`, {
        sessionId: this.state.sessionId
      });
      
      if (response.success) {
        this.updateState({
          simulatorStatus: 'STOPPING'
        });
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Failed to stop simulator:', error);
      return false;
    }
  }
  
  // Get market data
  public getMarketData(): Record<string, any> {
    return { ...this.marketData };
  }
  
  // Get orders
  public getOrders(): Record<string, any> {
    return { ...this.orders };
  }
  
  // Get portfolio
  public getPortfolio(): any {
    return this.portfolio ? { ...this.portfolio } : null;
  }
}