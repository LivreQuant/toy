// src/services/sse/exchange-data-stream.ts
import { SSEClient } from './sse-client';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/ws-manager';
import { EventEmitter } from '../../utils/event-emitter';
import { SessionManager } from '../session/session-manager';

export interface ExchangeDataOptions {
  baseUrl?: string;
  reconnectMaxAttempts?: number;
  symbols?: string[];
  debugMode?: boolean;
}

export interface MarketData {
  symbol: string;
  bid: number;
  ask: number;
  bidSize: number;
  askSize: number;
  lastPrice: number;
  lastSize: number;
  timestamp: number;
}

export interface OrderUpdate {
  orderId: string;
  symbol: string;
  status: string;
  filledQuantity: number;
  averagePrice: number;
}

export interface PortfolioPosition {
  symbol: string;
  quantity: number;
  averageCost: number;
  marketValue: number;
}

export interface PortfolioUpdate {
  positions: PortfolioPosition[];
  cashBalance: number;
  totalValue: number;
}

export class ExchangeDataStream extends EventEmitter {
  private sseClient: SSEClient;
  private sessionId: string | null = null;
  private symbols: string[] = [];
  private marketData: Record<string, MarketData> = {};
  private orders: Record<string, OrderUpdate> = {};
  private portfolio: PortfolioUpdate | null = null;
  private tokenManager: TokenManager;
  private webSocketManager: WebSocketManager;
  private debugMode: boolean;
  
  constructor(
    tokenManager: TokenManager, 
    webSocketManager: WebSocketManager,
    options: ExchangeDataOptions = {}
  ) {
    super();
    
    this.tokenManager = tokenManager;
    this.webSocketManager = webSocketManager;
    this.debugMode = options.debugMode || false;
    
    this.sseClient = new SSEClient(tokenManager, {
      reconnectMaxAttempts: options.reconnectMaxAttempts || 15,
      debugMode: this.debugMode
    });
    
    this.symbols = options.symbols || [];
  
    // Set up SSE client event listeners
    this.sseClient.on('message', this.handleServerEvent.bind(this));
    this.sseClient.on('market-data', this.handleMarketData.bind(this));
    this.sseClient.on('order-update', this.handleOrderUpdate.bind(this));
    this.sseClient.on('portfolio-update', this.handlePortfolioUpdate.bind(this));
    this.sseClient.on('error', this.handleError.bind(this));
    
    // Forward connection events from SSE client
    ['connected', 'disconnected', 'reconnecting', 'circuit_trip', 'circuit_closed'].forEach(event => {
      this.sseClient.on(event, (data: any) => this.emit(event, data));
    });
    
    // Listen to WebSocket connection events to coordinate
    this.webSocketManager.on('connected', this.handleWebSocketConnected.bind(this));
    this.webSocketManager.on('disconnected', this.handleWebSocketDisconnected.bind(this));
  }
  
  private handleWebSocketConnected(): void {
    // If WebSocket reconnected but SSE is disconnected, try to reconnect SSE
    if (this.sessionId && !this.isConnected()) {
      if (this.debugMode) {
        console.log('WebSocket connected, attempting to connect Exchange Data Stream');
      }
      this.connect(this.sessionId).catch(err => {
        console.error('Failed to reconnect Exchange Data Stream after WebSocket reconnection:', err);
      });
    }
  }
  
  private handleWebSocketDisconnected(): void {
    // Emit warning that data might be stale if WebSocket is disconnected
    this.emit('websocket_disconnected', {
      message: 'WebSocket disconnected, exchange data may be stale',
      timestamp: Date.now()
    });
  }
  
  public isConnected(): boolean {
    const status = this.sseClient.getConnectionStatus();
    return status.connected;
  }
  
  public async connect(sessionId: string, symbols?: string[]): Promise<boolean> {
    // Check WebSocket connection first
    if (!this.webSocketManager.getConnectionHealth().status) {
      this.emit('error', { 
        error: 'Cannot connect Exchange Data Stream - WebSocket is not connected',
        webSocketStatus: this.webSocketManager.getConnectionHealth().status
      });
      return false;
    }
    
    if (this.debugMode) {
      console.log('ExchangeDataStream - Connecting', { 
        sessionId, 
        symbols, 
        clientId: `exchange-data-${Date.now()}` 
      });
    }
  
    // Validate authentication first
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      this.emit('error', { error: 'Authentication required for exchange data stream' });
      return false;
    }
    
    if (this.debugMode) {
      console.log('ExchangeDataStream - Connecting with session ID:', sessionId);
    }
    this.sessionId = sessionId;
    
    // Update symbols if provided
    if (symbols) {
      if (this.debugMode) {
        console.log('ExchangeDataStream - Using symbols:', symbols);
      }
      this.symbols = symbols;
    }
    
    const params: Record<string, string> = {};
    if (this.symbols && this.symbols.length > 0) {
        params.symbols = this.symbols.join(',');
        if (this.debugMode) {
          console.log('ExchangeDataStream - Symbol parameter:', params.symbols);
        }
    }

    // Add client ID
    params.clientId = `exchange-data-${Date.now()}`;
    if (this.debugMode) {
      console.log('ExchangeDataStream - Client ID:', params.clientId);
    }
    
    try {
        const connected = await this.sseClient.connect(sessionId, params);
        if (this.debugMode) {
          console.log('ExchangeDataStream - Connection Result:', connected);
        }
        return connected;
    } catch (error) {
        console.error('ExchangeDataStream - Connection Error:', error);
        return false;
    }
  }
  
  private handleServerEvent(data: any): void {
    try {
        if (this.debugMode) {
          console.log('Received SSE data:', data);
        }

        // Check if data is in the expected format
        if (data && data.data) {
            if (this.debugMode) {
              console.log('Parsed SSE data:', data.data);
            }

            // Update market data
            if (data.data.market_data) {
                if (this.debugMode) {
                  console.log('Market Data:', data.data.market_data);
                }
                const marketDataMap: Record<string, MarketData> = {};
                data.data.market_data.forEach((item: MarketData) => {
                    if (this.debugMode) {
                      console.log('Individual Market Data Item:', item);
                    }
                    marketDataMap[item.symbol] = item;
                });
                this.marketData = marketDataMap;
                
                // Emit market data update
                this.emit('market-data-updated', this.marketData);
                if (this.debugMode) {
                  console.log('Emitted market data:', this.marketData);
                }
            }
            
            // Update orders if available
            if (data.data.order_updates) {
                if (this.debugMode) {
                  console.log('Order Updates:', data.data.order_updates);
                }
                const orderUpdates = data.data.order_updates;
                orderUpdates.forEach((update: OrderUpdate) => {
                    if (update.orderId) {
                        this.orders[update.orderId] = update;
                    }
                });
                
                this.emit('orders-updated', this.orders);
            }
            
            // Update portfolio if available
            if (data.data.portfolio) {
                if (this.debugMode) {
                  console.log('Portfolio Data:', data.data.portfolio);
                }
                this.portfolio = data.data.portfolio;
                this.emit('portfolio-updated', this.portfolio);
            }
        } else {
            console.warn('Received SSE data in unexpected format:', data);
        }
    } catch (error) {
        console.error('Error parsing SSE data:', error, 'Raw data:', data);
    }
  }

  public disconnect(): void {
    this.sseClient.close();
  }
  
  public getMarketData(): Record<string, MarketData> {
    return { ...this.marketData };
  }
  
  public getOrderUpdates(): Record<string, OrderUpdate> {
    return { ...this.orders };
  }
  
  public getPortfolio(): PortfolioUpdate | null {
    return this.portfolio ? { ...this.portfolio } : null;
  }
  
  private handleMarketData(data: any): void {
    if (Array.isArray(data)) {
      // Handle array of market data updates
      data.forEach(update => {
        if (update.symbol) {
          this.marketData[update.symbol] = update;
        }
      });
    } else if (data.symbol) {
      // Handle single market data update
      this.marketData[data.symbol] = data;
    }
    
    // Emit aggregated market data
    this.emit('market-data-updated', this.marketData);
  }
  
  private handleOrderUpdate(data: any): void {
    if (Array.isArray(data)) {
      // Handle array of order updates
      data.forEach(update => {
        if (update.orderId) {
          this.orders[update.orderId] = update;
        }
      });
    } else if (data.orderId) {
      // Handle single order update
      this.orders[data.orderId] = data;
    }
    
    // Emit aggregated order updates
    this.emit('orders-updated', this.orders);
  }
  
  private handlePortfolioUpdate(data: any): void {
    if (data && typeof data === 'object') {
      this.portfolio = data;
      
      // Emit portfolio update
      this.emit('portfolio-updated', this.portfolio);
    }
  }
  
  private handleError(error: any): void {
    console.error('Exchange data stream error:', error);
    this.emit('error', error);
  }
  
  // Method to update symbols being streamed
  public async updateSymbols(symbols: string[]): Promise<boolean> {
    this.symbols = symbols;
    
    // If already connected, reconnect with new symbols
    if (this.sessionId && this.isConnected()) {
      return this.connect(this.sessionId, symbols);
    }
    
    return true;
  }
  
  public getConnectionStatus(): {
    connected: boolean;
    connecting: boolean;
    webSocketConnected: boolean;
  } {
    const sseStatus = this.sseClient.getConnectionStatus();
    const wsStatus = this.webSocketManager.getConnectionHealth();
    
    return {
      connected: sseStatus.connected,
      connecting: sseStatus.connecting,
      webSocketConnected: wsStatus.status === 'connected'
    };
  }
  
  public dispose(): void {
    this.disconnect();
    this.removeAllListeners();
  }
}