// src/services/orders/order-manager.ts
import { getLogger } from '../../boot/logging';
import { TokenManager } from '../auth/token-manager';
import { OrdersApi, 
  OrderSubmissionRequest, OrderCancellationRequest, 
  EncodedOrderSubmissionRequest, EncodedOrderCancellationRequest,
  BatchOrderResponse, BatchCancelResponse } from '../../api/order';
import { toastService } from '../notification/toast-service';

export class OrderManager {
  private logger = getLogger('OrderManager');
  private ordersApi: OrdersApi;
  private tokenManager: TokenManager;

  constructor(ordersApi: OrdersApi, tokenManager: TokenManager) {
    this.ordersApi = ordersApi;
    this.tokenManager = tokenManager;
    this.logger.info('OrderManager initialized');
  }

  async submitOrders(submissionData: OrderSubmissionRequest): Promise<BatchOrderResponse> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Order submission attempted without authentication');
      toastService.error('Cannot submit orders: You are not logged in');
      
      return { 
        success: false, 
        errorMessage: 'Not authenticated',
        results: []
      };
    }

    if (!submissionData.orders || submissionData.orders.length === 0) {
      return {
        success: false,
        errorMessage: 'No orders provided',
        results: []
      };
    }

    const logContext = {
      orderCount: submissionData.orders.length,
      hasResearchFile: !!submissionData.researchFile,
      hasNotes: !!submissionData.notes,
      researchFileName: submissionData.researchFile?.name,
      researchFileSize: submissionData.researchFile?.size
    };

    this.logger.info('Attempting to submit orders with files', logContext);

    try {
      const response = await this.ordersApi.submitOrders(submissionData);

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
      }

      return response;
    } catch (error: any) {
      this.logger.error(`Exception during order submission`, {
        ...logContext,
        error: error.message
      });
      
      return {
        success: false,
        errorMessage: error instanceof Error ? error.message : String(error || 'Order submission failed unexpectedly'),
        results: []
      };
    }
  }

  async cancelOrders(cancelData: OrderCancellationRequest): Promise<BatchCancelResponse> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Order cancellation attempted without authentication');
      return { 
        success: false, 
        errorMessage: 'Not authenticated',
        results: []
      };
    }
  
    if (!cancelData.orderIds || cancelData.orderIds.length === 0) {
      return {
        success: false,
        errorMessage: 'No order IDs provided',
        results: []
      };
    }
  
    this.logger.info(`Attempting to cancel ${cancelData.orderIds.length} orders`);
  
    try {
      // Cancel orders via API - pass the orderIds array to the API
      const response = await this.ordersApi.cancelOrders(cancelData.orderIds);
  
      if (response.success) {
        this.logger.info(`Orders cancelled successfully`);
      } else {
        this.logger.warn(`Order cancellation failed: ${response.errorMessage}`);
        
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
      
      return {
        success: false,
        errorMessage: error instanceof Error ? error.message : String(error || 'Order cancellation failed unexpectedly'),
        results: []
      };
    }
  }

  async submitOrdersEncoded(submissionData: EncodedOrderSubmissionRequest): Promise<BatchOrderResponse> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Encoded order submission attempted without authentication');
      toastService.error('Cannot submit orders: You are not logged in');
      
      return { 
        success: false, 
        errorMessage: 'Not authenticated',
        results: []
      };
    }

    if (!submissionData.orders || !submissionData.orders.trim()) {
      return {
        success: false,
        errorMessage: 'No encoded orders provided',
        results: []
      };
    }

    const logContext = {
      ordersLength: submissionData.orders.length,
      hasResearchFile: !!submissionData.researchFile,
      hasNotes: !!submissionData.notes,
      researchFingerprintLength: submissionData.researchFile?.length
    };

    this.logger.info('Attempting to submit encoded orders', logContext);

    try {
      const response = await this.ordersApi.submitOrdersEncoded(submissionData);

      if (response.success) {
        this.logger.info(`Encoded orders submitted successfully`, {
          ...logContext,
          successCount: response.results.filter(r => r.success).length
        });
      } else {
        this.logger.warn(`Encoded order submission failed`, {
          ...logContext,
          error: response.errorMessage
        });
      }

      return response;
    } catch (error: any) {
      this.logger.error(`Exception during encoded order submission`, {
        ...logContext,
        error: error.message
      });
      
      return {
        success: false,
        errorMessage: error instanceof Error ? error.message : String(error || 'Encoded order submission failed unexpectedly'),
        results: []
      };
    }
  }

  async cancelOrdersEncoded(cancellationData: EncodedOrderCancellationRequest): Promise<BatchCancelResponse> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Encoded order cancellation attempted without authentication');
      return { 
        success: false, 
        errorMessage: 'Not authenticated',
        results: []
      };
    }

    if (!cancellationData.orderIds || !cancellationData.orderIds.trim()) {
      return {
        success: false,
        errorMessage: 'No encoded order IDs provided',
        results: []
      };
    }

    const logContext = {
      orderIdsLength: cancellationData.orderIds.length,
      hasResearchFile: !!cancellationData.researchFile,
      hasNotes: !!cancellationData.notes,
      researchFingerprintLength: cancellationData.researchFile?.length
    };

    this.logger.info(`Attempting to cancel encoded orders`, logContext);

    try {
      const response = await this.ordersApi.cancelOrdersEncoded(cancellationData);

      if (response.success) {
        this.logger.info(`Encoded orders cancelled successfully`, logContext);
      } else {
        this.logger.warn(`Encoded order cancellation failed: ${response.errorMessage}`, logContext);
      }

      return response;
    } catch (error: any) {
      this.logger.error(`Exception during encoded order cancellation`, {
        ...logContext,
        error: error.message
      });
      
      return {
        success: false,
        errorMessage: error instanceof Error ? error.message : String(error || 'Encoded order cancellation failed unexpectedly'),
        results: []
      };
    }
  }
}