// src/services/sse/exchange-data-stream.ts
import { SSEManager } from './sse-manager';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { EventEmitter } from '../../utils/event-emitter';

export interface ExchangeDataOptions {
  reconnectMaxAttempts?: number;
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
  private sseManager: SSEManager;
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
    
    this.sseManager = new SSEManager(tokenManager, {
      reconnectMaxAttempts: options.reconnectMaxAttempts || 15,
      debugMode: this.debugMode
    });
  
    // Set up SSE manager event listeners
    this.sseManager.on('exchange-data', this.handleExchangeData.bind(this));
    this.sseManager.on('error', this.handleError.bind(this));
    
    // Forward connection events from SSE manager
    ['connected', 'disconnected', 'reconnecting', 'circuit_trip', 'circuit_closed'].forEach(event => {
      this.sseManager.on(event, (data: any) => this.emit(event, data));
    });
    
    // Listen to WebSocket connection events to coordinate
    this.webSocketManager.on('connected', this.handleWebSocketConnected.bind(this));
    this.webSocketManager.on('disconnected', this.handleWebSocketDisconnected.bind(this));
  }
  
  private handleWebSocketConnected(): void {
    // If WebSocket reconnected but SSE is disconnected, try to reconnect SSE
    if (!this.isConnected()) {
      if (this.debugMode) {
        console.log('WebSocket connected, attempting to connect Exchange Data Stream');
      }
      this.connect().catch(err => {
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
    const status = this.sseManager.getConnectionStatus();
    return status.connected;
  }
  
  public async connect(): Promise<boolean> {
    // Check WebSocket connection first
    if (!this.webSocketManager.getConnectionHealth().status) {
      this.emit('error', { 
        error: 'Cannot connect Exchange Data Stream - WebSocket is not connected',
        webSocketStatus: this.webSocketManager.getConnectionHealth().status
      });
      return false;
    }
    
    if (this.debugMode) {
      console.log('ExchangeDataStream - Connecting to unified data stream');
    }
  
    // Validate authentication first
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      this.emit('error', { error: 'Authentication required for exchange data stream' });
      return false;
    }
    
    try {
        const connected = await this.sseManager.connect();
        if (this.debugMode) {
          console.log('ExchangeDataStream - Connection Result:', connected);
        }
        return connected;
    } catch (error) {
        console.error('ExchangeDataStream - Connection Error:', error);
        return false;
    }
  }
  
  private handleExchangeData(data: any): void {
    try {
        if (this.debugMode) {
          console.log('Received exchange data:', data);
        }

        // Update market data
        if (data.market_data) {
            if (this.debugMode) {
              console.log('Market Data:', data.market_data);
            }
            const marketDataMap: Record<string, MarketData> = {};
            data.market_data.forEach((item: MarketData) => {
                marketDataMap[item.symbol] = item;
            });
            this.marketData = marketDataMap;
            
            // Emit market data update
            this.emit('market-data-updated', this.marketData);
        }
        
        // Update orders if available
        if (data.order_updates) {
            if (this.debugMode) {
              console.log('Order Updates:', data.order_updates);
            }
            const orderUpdates = data.order_updates;
            orderUpdates.forEach((update: OrderUpdate) => {
                if (update.orderId) {
                    this.orders[update.orderId] = update;
                }
            });
            
            this.emit('orders-updated', this.orders);
        }
        
        // Update portfolio if available
        if (data.portfolio) {
            if (this.debugMode) {
              console.log('Portfolio Data:', data.portfolio);
            }
            this.portfolio = data.portfolio;
            this.emit('portfolio-updated', this.portfolio);
        }
    } catch (error) {
        console.error('Error processing exchange data:', error, 'Raw data:', data);
    }
  }

  public disconnect(): void {
    this.sseManager.close();
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
  
  private handleError(error: any): void {
    console.error('Exchange data stream error:', error);
    this.emit('error', error);
  }
  
  public getConnectionStatus(): {
    connected: boolean;
    connecting: boolean;
    webSocketConnected: boolean;
  } {
    const sseStatus = this.sseManager.getConnectionStatus();
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