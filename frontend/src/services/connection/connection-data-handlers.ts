// src/services/connection/connection-data-handlers.ts

import { HttpClient } from '../../api/http-client';
import { OrdersApi } from '../../api/order';
// *** Use the imported ErrorHandler instance, not static calls ***
import { ErrorHandler, ErrorSeverity } from '../../utils/error-handler'; // Keep imports
import { Logger } from '../../utils/logger'; // Optional: Add logger if needed for data handling logic

export class ConnectionDataHandlers {
  private exchangeData: Record<string, any> = {};
  private ordersApi: OrdersApi;
  // +++ ADDED: Store the injected ErrorHandler instance +++
  private errorHandler: ErrorHandler;
  // Optional: Add logger instance if needed
  // private logger: Logger;

  // +++ MODIFIED: Add errorHandler parameter +++
  // Optional: Add logger parameter if needed
  constructor(
    httpClient: HttpClient,
    errorHandler: ErrorHandler
    // logger?: Logger // Optional logger injection
  ) {
    this.ordersApi = new OrdersApi(httpClient);
    // +++ ADDED: Assign the injected instance +++
    this.errorHandler = errorHandler;
    // Optional: Assign logger
    // this.logger = logger || Logger.getInstance(); // Use injected or default logger
  }

  /**
   * Updates the internal cache of exchange data.
   * @param data - The new exchange data.
   */
  public updateExchangeData(data: Record<string, any>): void {
    // Consider deep merging or specific updates based on data structure if needed
    this.exchangeData = { ...this.exchangeData, ...data };
    // Optional: Log data update
    // this.logger?.info('Exchange data updated');
  }

  /**
   * Retrieves a copy of the cached exchange data.
   * @returns A copy of the exchange data object.
   */
  public getExchangeData(): Record<string, any> {
    // Return a copy to prevent external modification
    return { ...this.exchangeData };
  }


  /**
   * Submits a trading order via the OrdersApi.
   * Handles API errors using the injected ErrorHandler.
   * @param order - The order details.
   * @returns A promise resolving to the submission result.
   */
  public async submitOrder(order: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price?: number;
    type: 'MARKET' | 'LIMIT';
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
    try {
      // Add idempotency key if your API supports it
      const requestId = `order-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
      const response = await this.ordersApi.submitOrder({
        ...order,
        requestId // Include the request ID
      });

      if (!response.success) {
        // *** MODIFIED: Use the injected errorHandler instance ***
        const errorMsg = response.errorMessage || `Failed to submit ${order.type} ${order.side} order for ${order.symbol}`;
        this.errorHandler.handleDataError(
          errorMsg,
          ErrorSeverity.MEDIUM, // Or HIGH depending on severity
          'OrderSubmission' // Specific context
        );
      }

      return {
        success: response.success,
        orderId: response.orderId,
        error: response.errorMessage // Pass back specific API error message if available
      };
    } catch (error) {
      // Handle exceptions during the API call
      const errorMessage = error instanceof Error ? error.message : 'Order submission failed due to an unexpected error';

      // *** MODIFIED: Use the injected errorHandler instance ***
      this.errorHandler.handleDataError(
        error, // Pass the actual error object for better logging context
        ErrorSeverity.HIGH, // Exceptions are typically high severity
        'OrderSubmissionException' // Context indicating an exception occurred
      );

      return {
        success: false,
        error: errorMessage // Return a user-friendly message derived from the exception
      };
    }
  }

  /**
   * Cancels a trading order via the OrdersApi.
   * Handles API errors using the injected ErrorHandler.
   * @param orderId - The ID of the order to cancel.
   * @returns A promise resolving to the cancellation result.
   */
  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await this.ordersApi.cancelOrder(orderId);

      if (!response.success) {
        // *** MODIFIED: Use the injected errorHandler instance ***
        const errorMsg = `Failed to cancel order ${orderId}`;
        this.errorHandler.handleDataError(
          errorMsg,
          ErrorSeverity.MEDIUM,
          'OrderCancellation'
        );
        return { success: false, error: errorMsg }; // Return specific error
      }

      // Success case
      return { success: true };

    } catch (error) {
      // Handle exceptions during the API call
      const errorMessage = error instanceof Error ? error.message : 'Order cancellation failed due to an unexpected error';

      // *** MODIFIED: Use the injected errorHandler instance ***
      this.errorHandler.handleDataError(
        error, // Pass the actual error object
        ErrorSeverity.HIGH, // Exceptions are typically high severity
        'OrderCancellationException' // Context indicating an exception occurred
      );

      return {
        success: false,
        error: errorMessage // Return a user-friendly message
      };
    }
  }
}
