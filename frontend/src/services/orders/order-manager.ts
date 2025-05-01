// src/services/orders/order-manager.ts
import { getLogger } from '../../boot/logging';
import { TokenManager } from '../auth/token-manager';
import { OrdersApi } from '../../api/order';

// Define the types we need
interface OrderRequest {
  symbol: string;
  side: 'BUY' | 'SELL';
  type: 'MARKET' | 'LIMIT';
  quantity: number;
  price?: number;
  requestId?: string;
}

interface OrderResult {
  success: boolean;
  orderId?: string;
  errorMessage?: string;
}

interface BatchResponse {
  success: boolean;
  results: OrderResult[];
  errorMessage?: string;
}

interface CancelResult {
  orderId: string;
  success: boolean;
  errorMessage?: string;
}

interface BatchCancelResponse {
  success: boolean;
  results: CancelResult[];
  errorMessage?: string;
}

export class OrderManager {
  private logger = getLogger('OrderManager');
  private ordersApi: OrdersApi;
  private tokenManager: TokenManager;

  constructor(ordersApi: OrdersApi, tokenManager: TokenManager) {
    this.ordersApi = ordersApi;
    this.tokenManager = tokenManager;
    this.logger.info('OrderManager initialized');
  }

  async submitOrders(orders: OrderRequest[]): Promise<BatchResponse> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Order submission attempted without authentication');
      return { 
        success: false, 
        errorMessage: 'Not authenticated',
        results: []
      };
    }

    if (!orders || orders.length === 0) {
      return {
        success: false,
        errorMessage: 'No orders provided',
        results: []
      };
    }

    const logContext = {
      orderCount: orders.length,
      firstSymbol: orders[0].symbol,
      firstSide: orders[0].side
    };

    this.logger.info('Attempting to submit orders', logContext);

    try {
      // Submit orders to API
      const response = await this.ordersApi.submitOrders(orders);

      if (response.success) {
        this.logger.info(`Orders submitted successfully`, {
          ...logContext,
          successCount: response.results.filter(r => r.success).length
        });
      } else {
        this.logger.warn(`Order submission failed`, {
          ...logContext,
          error: response.errorMessage
        });
        
        // Return error with empty results array
        return {
          success: false,
          errorMessage: response.errorMessage || 'Failed to submit orders',
          results: []
        };
      }

      return response;
    } catch (error: any) {
      this.logger.error(`Exception during order submission`, {
        ...logContext,
        error: error.message
      });
      
      // Return error with empty results array
      return {
        success: false,
        errorMessage: error instanceof Error ? error.message : String(error || 'Order submission failed unexpectedly'),
        results: []
      };
    }
  }

  async cancelOrders(orderIds: string[]): Promise<BatchCancelResponse> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Order cancellation attempted without authentication');
      return { 
        success: false, 
        errorMessage: 'Not authenticated',
        results: []
      };
    }

    if (!orderIds || orderIds.length === 0) {
      return {
        success: false,
        errorMessage: 'No order IDs provided',
        results: []
      };
    }

    this.logger.info(`Attempting to cancel ${orderIds.length} orders`);

    try {
      // Cancel orders via API
      const response = await this.ordersApi.cancelOrders(orderIds);

      if (response.success) {
        this.logger.info(`Orders cancelled successfully`);
      } else {
        this.logger.warn(`Order cancellation failed: ${response.errorMessage}`);
        
        // Return error with empty results array
        return {
          success: false,
          errorMessage: response.errorMessage || 'Failed to cancel orders',
          results: []
        };
      }

      return response;
    } catch (error: any) {
      this.logger.error(`Exception during order cancellation`, {
        error: error.message
      });
      
      // Return error with empty results array
      return {
        success: false,
        errorMessage: error instanceof Error ? error.message : String(error || 'Order cancellation failed unexpectedly'),
        results: []
      };
    }
  }
}