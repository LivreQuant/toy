// src/services/connection/connection-data-handlers.ts
import { HttpClient } from '../../api/http-client';
import { OrdersApi } from '../../api/order';
import { ErrorHandler, ErrorSeverity } from '../../utils/error-handler';

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

  
  public async submitOrder(order: {
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
      
      if (!response.success) {
        ErrorHandler.handleDataError(
          response.errorMessage || 'Failed to submit order',
          ErrorSeverity.MEDIUM,
          'Order'
        );
      }
      
      return { 
        success: response.success, 
        orderId: response.orderId,
        error: response.errorMessage
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Order submission failed';
      
      ErrorHandler.handleDataError(
        errorMessage,
        ErrorSeverity.MEDIUM,
        'Order'
      );
      
      return { 
        success: false, 
        error: errorMessage
      };
    }
  }

  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await this.ordersApi.cancelOrder(orderId);
      
      if (!response.success) {
        ErrorHandler.handleDataError(
          'Failed to cancel order',
          ErrorSeverity.MEDIUM,
          'Order'
        );
      }
      
      return { 
        success: response.success,
        error: response.success ? undefined : 'Failed to cancel order'
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Order cancellation failed';
      
      ErrorHandler.handleDataError(
        errorMessage,
        ErrorSeverity.MEDIUM,
        'Order'
      );
      
      return { 
        success: false, 
        error: errorMessage 
      };
    }
  }
}