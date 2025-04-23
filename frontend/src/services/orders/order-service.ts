// src/services/orders/order-service.ts
import { TokenManager } from '../auth/token-manager';
import { OrdersApi, OrderSide, OrderType, SubmitOrderRequest } from '../../api/order';
import { getLogger } from '../../boot/logging';
import { handleError } from '../../utils/error-handling';

export class OrderService {
  private logger = getLogger('OrderService');
  private ordersApi: OrdersApi;
  private tokenManager: TokenManager;

  constructor(ordersApi: OrdersApi, tokenManager: TokenManager) {
    this.ordersApi = ordersApi;
    this.tokenManager = tokenManager;
    this.logger.info('OrderService initialized');
  }

  async submitOrder(order: {
    symbol: string;
    side: OrderSide;
    quantity: number;
    price?: number;
    type: OrderType;
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Order submission attempted without authentication');
      return { 
        success: false, 
        error: 'Not authenticated' 
      };
    }

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
      
      const submitRequest: SubmitOrderRequest = {
        ...order,
        requestId
      };

      const response = await this.ordersApi.submitOrder(submitRequest);

      if (response.success) {
        this.logger.info(`Order submitted successfully`, {
          ...logContext,
          orderId: response.orderId
        });
      } else {
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

  async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Order cancellation attempted without authentication');
      return { 
        success: false, 
        error: 'Not authenticated' 
      };
    }

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