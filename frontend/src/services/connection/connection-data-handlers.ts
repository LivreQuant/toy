// src/services/connection/connection-data-handlers.ts
import { HttpClient } from '../../api/http-client';
import { OrdersApi } from '../../api/order';

export class ConnectionDataHandlers {
  private exchangeData: Record<string, any> = {};
  private ordersApi: OrdersApi;

  constructor(httpClient: HttpClient) {
    this.ordersApi = new OrdersApi(httpClient);
  }

  public updateExchangeData(data: Record<string, any>): void {
    this.exchangeData = { ...data };
  }

  public getExchangeData(): Record<string, any> {
    return { ...this.exchangeData };
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
      const response = await this.ordersApi.cancelOrder(orderId);
      
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