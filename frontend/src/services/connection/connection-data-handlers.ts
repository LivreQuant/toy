// src/services/connection/connection-data-handlers.ts
import { MarketData, OrderUpdate, PortfolioUpdate } from '../sse/exchange-data-stream';
import { OrdersApi } from '../../api/order';
import { HttpClient } from '../../api/http-client';

export class ConnectionDataHandlers {
  private marketData: Record<string, MarketData> = {};
  private orders: Record<string, OrderUpdate> = {};
  private portfolio: PortfolioUpdate | null = null;
  private ordersApi: OrdersApi;

  constructor(httpClient: HttpClient) {
    this.ordersApi = new OrdersApi(httpClient);
  }

  public updateMarketData(data: Record<string, MarketData>): void {
    this.marketData = { ...data };
  }

  public updateOrders(data: Record<string, OrderUpdate>): void {
    this.orders = { ...data };
  }

  public updatePortfolio(data: PortfolioUpdate): void {
    this.portfolio = { ...data };
  }

  public getMarketData(): Record<string, MarketData> {
    return { ...this.marketData };
  }

  public getOrders(): Record<string, OrderUpdate> {
    return { ...this.orders };
  }

  public getPortfolio(): PortfolioUpdate | null {
    return this.portfolio ? { ...this.portfolio } : null;
  }

  public async submitOrder(sessionId: string, order: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price?: number;
    type: 'MARKET' | 'LIMIT';
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
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

  public async cancelOrder(sessionId: string, orderId: string): Promise<{ success: boolean; error?: string }> {
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