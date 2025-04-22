// src/services/connection/data-handlers.ts
import { HttpClient } from '../../api/http-client';
import { OrdersApi, OrderSide, OrderType } from '../../api/order';
import { getLogger } from '../../boot/logging';
import { handleError } from '../../utils/error-handling';

export class DataHandlers {
  private logger = getLogger('DataHandlers');
  private ordersApi: OrdersApi;
  private exchangeData: Record<string, any> = {}; // Internal cache for data if needed
  
  constructor(httpClient: HttpClient) {
    this.ordersApi = new OrdersApi(httpClient);
    this.logger.info('DataHandlers initialized');
  }

  /**
   * Updates the internal cache of exchange data.
   * @param data - The new exchange data.
   */
  public updateExchangeData(data: Record<string, any>): void {
    this.exchangeData = { ...this.exchangeData, ...data };
    this.logger.debug('Internal exchange data cache updated');
  }

  /**
   * Retrieves a copy of the cached exchange data.
   * @returns A copy of the exchange data object.
   */
  public getExchangeData(): Record<string, any> {
    return { ...this.exchangeData };
  }

  /**
   * Submits a trading order via the OrdersApi.
   * @param order - The order details.
   * @returns A promise resolving to the submission result.
   */
  public async submitOrder(order: {
    symbol: string;
    side: OrderSide;
    quantity: number;
    price?: number;
    type: OrderType;
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
    const logContext = {
      symbol: order.symbol,
      side: order.side,
      type: order.type,
      quantity: order.quantity
    };
    
    this.logger.info('Attempting to submit order', logContext);

    // Basic client-side validation
    if (order.type === 'LIMIT' && (typeof order.price !== 'number' || order.price <= 0)) {
      const errorMsg = 'Invalid limit price for LIMIT order.';
      return handleError(errorMsg, 'SubmitOrderValidation', 'low', logContext);
    }
    
    if (typeof order.quantity !== 'number' || order.quantity <= 0) {
      const errorMsg = 'Invalid order quantity.';
      return handleError(errorMsg, 'SubmitOrderValidation', 'low', logContext);
    }

    try {
      // Add idempotency key
      const requestId = `order-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      
      const response = await this.ordersApi.submitOrder({
        ...order,
        requestId
      });

      if (response.success) {
        this.logger.info(`Order submitted successfully`, {
          ...logContext,
          orderId: response.orderId
        });
      } else {
        // Log API-reported failure
        this.logger.warn(`Order submission failed via API`, {
          ...logContext,
          error: response.errorMessage
        });
        
        return handleError(
          response.errorMessage || `Failed to submit ${order.type} ${order.side} order for ${order.symbol}`,
          'OrderSubmissionApiFail',
          'medium',
          { orderDetails: logContext }
        );
      }

      return {
        success: response.success,
        orderId: response.orderId,
        error: response.errorMessage
      };
    } catch (error: any) {
      // Handle exceptions during the API call
      this.logger.error(`Exception during order submission`, {
        ...logContext,
        error: error.message
      });
      
      return handleError(
        error instanceof Error ? error.message : String(error || 'Order submission failed unexpectedly'),
        'OrderSubmissionException',
        'high',
        { orderDetails: logContext }
      );
    }
  }

  /**
   * Cancels a trading order via the OrdersApi.
   * @param orderId - The ID of the order to cancel.
   * @returns A promise resolving to the cancellation result.
   */
  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
    this.logger.info(`Attempting to cancel order: ${orderId}`);

    if (!orderId) {
      const errorMsg = "Cannot cancel order: No Order ID provided.";
      return handleError(errorMsg, 'CancelOrderValidation', 'low');
    }

    try {
      const response = await this.ordersApi.cancelOrder(orderId);

      if (response.success) {
        this.logger.info(`Order cancellation request successful for ID: ${orderId}`);
      } else {
        const errorMsg = `API failed to cancel order ${orderId}`;
        this.logger.warn(errorMsg, { orderId });
        
        return handleError(errorMsg, 'OrderCancellationApiFail', 'medium', { orderId });
      }

      return { success: true };
    } catch (error: any) {
      // Handle exceptions during the API call
      this.logger.error(`Exception during order cancellation for ID: ${orderId}`, {
        error: error.message
      });
      
      return handleError(
        error instanceof Error ? error.message : String(error || 'Order cancellation failed unexpectedly'),
        'OrderCancellationException',
        'high',
        { orderId }
      );
    }
  }
}