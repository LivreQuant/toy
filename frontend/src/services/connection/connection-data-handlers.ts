// src/services/connection/connection-data-handlers.ts
import { HttpClient } from '../../api/http-client';
import { OrdersApi, OrderSide, OrderType } from '../../api/order'; // Import types
// Import the specific ErrorHandler instance/singleton access
import { AppErrorHandler } from '../../utils/app-error-handler';
import { ErrorSeverity } from '../../utils/error-handler';
import { EnhancedLogger } from '../../utils/enhanced-logger';
import { getLogger } from '../../boot/logging';

export class ConnectionDataHandlers {
  private exchangeData: Record<string, any> = {}; // Internal cache for data if needed
  private ordersApi: OrdersApi;
  // ErrorHandler instance is retrieved via AppErrorHandler singleton
  // private errorHandler: ErrorHandler; // No need to store if using static methods
  private logger: EnhancedLogger;

  constructor(
    httpClient: HttpClient
    // ErrorHandler is accessed via static AppErrorHandler.getInstance()
    // Logger is obtained via getLogger
  ) {
    this.ordersApi = new OrdersApi(httpClient);
    this.logger = getLogger('ConnectionDataHandlers'); // Get logger instance
    this.logger.info('ConnectionDataHandlers initialized');
  }

  /**
   * Updates the internal cache of exchange data (if used).
   * @param data - The new exchange data.
   */
  public updateExchangeData(data: Record<string, any>): void {
    // Simple merge, consider deep merging or specific updates if needed
    this.exchangeData = { ...this.exchangeData, ...data };
    this.logger.debug('Internal exchange data cache updated');
  }

  /**
   * Retrieves a copy of the cached exchange data (if used).
   * @returns A copy of the exchange data object.
   */
  public getExchangeData(): Record<string, any> {
    // Return a copy to prevent external modification
    return { ...this.exchangeData };
  }


  /**
   * Submits a trading order via the OrdersApi.
   * Handles API errors using AppErrorHandler.
   * @param order - The order details.
   * @returns A promise resolving to the submission result.
   */
  public async submitOrder(order: {
    symbol: string;
    side: OrderSide;
    quantity: number;
    price?: number; // Required for LIMIT orders
    type: OrderType;
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
    const logContext = { symbol: order.symbol, side: order.side, type: order.type, quantity: order.quantity };
    this.logger.info('Attempting to submit order', logContext);

    // Basic client-side validation (more robust validation recommended)
    if (order.type === 'LIMIT' && (typeof order.price !== 'number' || order.price <= 0)) {
        const errorMsg = 'Invalid limit price for LIMIT order.';
        this.logger.error(errorMsg, logContext);
        AppErrorHandler.handleDataError(errorMsg, ErrorSeverity.LOW, 'SubmitOrderValidation');
        return { success: false, error: errorMsg };
    }
     if (typeof order.quantity !== 'number' || order.quantity <= 0) {
         const errorMsg = 'Invalid order quantity.';
         this.logger.error(errorMsg, logContext);
         AppErrorHandler.handleDataError(errorMsg, ErrorSeverity.LOW, 'SubmitOrderValidation');
         return { success: false, error: errorMsg };
     }


    try {
      // Add idempotency key using a simple timestamp/random combo
      const requestId = `order-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const response = await this.ordersApi.submitOrder({
        ...order,
        requestId // Include the request ID
      });

      if (response.success) {
          this.logger.info(`Order submitted successfully`, { ...logContext, orderId: response.orderId });
      } else {
          // Log API-reported failure and notify user via error handler
          this.logger.warn(`Order submission failed via API`, { ...logContext, error: response.errorMessage });
          AppErrorHandler.handleDataError(
            response.errorMessage || `Failed to submit ${order.type} ${order.side} order for ${order.symbol}`,
            ErrorSeverity.MEDIUM,
            'OrderSubmissionApiFail',
            { orderDetails: logContext } // Pass details to handler
          );
      }

      // Return the result from the API
      return {
        success: response.success,
        orderId: response.orderId,
        error: response.errorMessage
      };

    } catch (error: any) {
      // Handle exceptions during the API call itself (e.g., network error bubbled up)
      this.logger.error(`Exception during order submission`, { ...logContext, error: error.message });
      const errorToHandle = error instanceof Error ? error : new Error(String(error) || 'Order submission failed unexpectedly');
      // Use handleGenericError or handleConnectionError depending on the expected error type from HttpClient
       AppErrorHandler.handleGenericError(
           errorToHandle,
           ErrorSeverity.HIGH, // Exceptions during submission are usually high severity
           'OrderSubmissionException',
           { orderDetails: logContext }
       );

      return {
        success: false,
        error: errorToHandle.message // Return the exception message
      };
    }
  }

  /**
   * Cancels a trading order via the OrdersApi.
   * Handles API errors using AppErrorHandler.
   * @param orderId - The ID of the order to cancel.
   * @returns A promise resolving to the cancellation result.
   */
  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
      this.logger.info(`Attempting to cancel order: ${orderId}`);

      if (!orderId) {
          const errorMsg = "Cannot cancel order: No Order ID provided.";
          this.logger.error(errorMsg);
          AppErrorHandler.handleDataError(errorMsg, ErrorSeverity.LOW, 'CancelOrderValidation');
          return { success: false, error: errorMsg };
      }

      try {
          const response = await this.ordersApi.cancelOrder(orderId);

          if (response.success) {
              this.logger.info(`Order cancellation request successful for ID: ${orderId}`);
          } else {
              // Log API-reported failure and notify user
               const errorMsg = `API failed to cancel order ${orderId}`; // More generic message from API needed ideally
               this.logger.warn(errorMsg, { orderId });
               // Assume API doesn't return specific error message here, adjust if it does
              AppErrorHandler.handleDataError(
                errorMsg,
                ErrorSeverity.MEDIUM,
                'OrderCancellationApiFail',
                { orderId }
              );
               // Return failure, but API might not provide detailed error
               return { success: false, error: errorMsg };
          }

          return { success: true }; // Return success

      } catch (error: any) {
          // Handle exceptions during the API call
           this.logger.error(`Exception during order cancellation for ID: ${orderId}`, { error: error.message });
           const errorToHandle = error instanceof Error ? error : new Error(String(error) || 'Order cancellation failed unexpectedly');
           AppErrorHandler.handleGenericError(
               errorToHandle,
               ErrorSeverity.HIGH,
               'OrderCancellationException',
               { orderId }
           );

          return {
            success: false,
            error: errorToHandle.message
          };
      }
  }
}