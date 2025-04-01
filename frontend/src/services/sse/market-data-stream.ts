import { SSEClient } from './sse-client';
import { TokenManager } from '../auth/token-manager';
import { EventEmitter } from '../../utils/event-emitter';

export interface MarketDataOptions {
  baseUrl?: string;
  reconnectMaxAttempts?: number;
  symbols?: string[];
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

export class MarketDataStream extends EventEmitter {
  private sseClient: SSEClient;
  private sessionId: string | null = null;
  private symbols: string[] = [];
  private marketData: Record<string, MarketData> = {};
  private orders: Record<string, OrderUpdate> = {};
  private portfolio: PortfolioUpdate | null = null;
  private tokenManager: TokenManager;
  
  constructor(tokenManager: TokenManager, options: MarketDataOptions = {}) {
    super();
    
    this.tokenManager = tokenManager;
    this.sseClient = new SSEClient(tokenManager, {
      reconnectMaxAttempts: options.reconnectMaxAttempts || 15
    });
    
    this.symbols = options.symbols || [];
  
    // Set up event listeners in the constructor
    this.sseClient.on('message', this.handleServerEvent.bind(this));
    
    // Set up event listeners
    this.sseClient.on('market-data', this.handleMarketData.bind(this));
    this.sseClient.on('order-update', this.handleOrderUpdate.bind(this));
    this.sseClient.on('portfolio-update', this.handlePortfolioUpdate.bind(this));
    this.sseClient.on('error', this.handleError.bind(this));
    
    // Forward connection events
    ['connected', 'disconnected', 'reconnecting', 'circuit_trip', 'circuit_closed'].forEach(event => {
      this.sseClient.on(event, (data: any) => this.emit(event, data));
    });
  }
  
  public async connect(sessionId: string, symbols?: string[]): Promise<boolean> {
    console.log('MarketDataStream - Connecting', { 
      sessionId, 
      symbols, 
      clientId: `market-data-${Date.now()}` 
    });
  
    // Validate authentication first
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      this.emit('error', { error: 'Authentication required for market data stream' });
      return false;
    }
    
    console.log('MarketDataStream - Connecting with session ID:', sessionId);
    this.sessionId = sessionId;
    
    // Update symbols if provided
    if (symbols) {
      console.log('MarketDataStream - Using symbols:', symbols);
      this.symbols = symbols;
    }
    
    const params: Record<string, string> = {};
    if (symbols && symbols.length > 0) {
        params.symbols = symbols.join(',');
        console.log('MarketDataStream - Symbol parameter:', params.symbols);
    }

    // Add client ID
    params.clientId = `market-data-${Date.now()}`;
    console.log('MarketDataStream - Client ID:', params.clientId);
    
    try {
        const connected = await this.sseClient.connect(sessionId, params);
        console.log('MarketDataStream - Connection Result:', connected);
        return connected;
    } catch (error) {
        console.error('MarketDataStream - Connection Error:', error);
        return false;
    }
  }
  
  private handleServerEvent(data: any): void {
    try {
        console.log('Received SSE data:', data);

        // Check if data is in the expected format
        if (data && data.data) {
            console.log('Parsed SSE data:', data.data);

            // Update market data
            if (data.data.market_data) {
                console.log('Market Data:', data.data.market_data);
                const marketDataMap: Record<string, MarketData> = {};
                data.data.market_data.forEach((item: MarketData) => {
                    console.log('Individual Market Data Item:', item);
                    marketDataMap[item.symbol] = item;
                });
                this.marketData = marketDataMap;
                
                // Emit market data update
                this.emit('market-data-updated', this.marketData);
                console.log('Emitted market data:', this.marketData);
            }
            
            // Update portfolio if available
            if (data.data.portfolio) {
                console.log('Portfolio Data:', data.data.portfolio);
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
    console.error('Market data stream error:', error);
    this.emit('error', error);
  }
}