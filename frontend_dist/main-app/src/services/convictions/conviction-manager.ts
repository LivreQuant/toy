// frontend_dist/main-app/src/services/convictions/conviction-manager.ts
import { getLogger } from '../../boot/logging';
import { TokenManager } from '@trading-app/auth';
import { 
  ConvictionClient,
  ConvictionSubmissionRequest, 
  ConvictionCancellationRequest, 
  EncodedConvictionSubmissionRequest, 
  EncodedConvictionCancellationRequest,
  BatchConvictionResponse, 
  BatchCancelResponse 
} from '@trading-app/api';
import { toastService } from '../notification/toast-service';

export class ConvictionManager {
  private logger = getLogger('ConvictionManager');
  private convictionsApi: ConvictionClient;
  private tokenManager: TokenManager;

  constructor(convictionsApi: ConvictionClient, tokenManager: TokenManager) {
    this.convictionsApi = convictionsApi;
    this.tokenManager = tokenManager;
    this.logger.info('ConvictionManager initialized');
  }

  async submitConvictions(submissionData: ConvictionSubmissionRequest): Promise<BatchConvictionResponse> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Conviction submission attempted without authentication');
      toastService.error('Cannot submit convictions: You are not logged in');
      
      return { 
        success: false, 
        errorMessage: 'Not authenticated',
        results: []
      };
    }

    if (!submissionData.convictions || submissionData.convictions.length === 0) {
      return {
        success: false,
        errorMessage: 'No convictions provided',
        results: []
      };
    }

    const logContext = {
      convictionCount: submissionData.convictions.length,
      hasResearchFile: !!submissionData.researchFile,
      hasNotes: !!submissionData.notes,
      researchFileName: submissionData.researchFile?.name,
      researchFileSize: submissionData.researchFile?.size
    };

    this.logger.info('Attempting to submit convictions with files', logContext);

    try {
      const response = await this.convictionsApi.submitConvictions(submissionData);

      if (response.success) {
        this.logger.info(`Convictions submitted successfully`, {
          ...logContext,
          successCount: response.results.filter(r => r.success).length
        });
      } else {
        this.logger.warn(`Conviction submission failed`, {
          ...logContext,
          error: response.errorMessage
        });
      }

      return response;
    } catch (error: any) {
      this.logger.error(`Exception during conviction submission`, {
        ...logContext,
        error: error.message
      });
      
      return {
        success: false,
        errorMessage: error instanceof Error ? error.message : String(error || 'Conviction submission failed unexpectedly'),
        results: []
      };
    }
  }
  
  async cancelConvictions(cancelData: ConvictionCancellationRequest): Promise<BatchCancelResponse> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Conviction cancellation attempted without authentication');
      return { 
        success: false, 
        errorMessage: 'Not authenticated',
        results: []
      };
    }
  
    if (!cancelData.convictionIds || cancelData.convictionIds.length === 0) {
      return {
        success: false,
        errorMessage: 'No conviction IDs provided',
        results: []
      };
    }
  
    this.logger.info(`Attempting to cancel ${cancelData.convictionIds.length} convictions`);
  
    try {
      // Cancel convictions via API - pass the full cancelData object to the API
      const response = await this.convictionsApi.cancelConvictions(cancelData);
  
      if (response.success) {
        this.logger.info(`Convictions cancelled successfully`);
      } else {
        this.logger.warn(`Conviction cancellation failed: ${response.errorMessage}`);
        
        return {
          success: false,
          errorMessage: response.errorMessage || 'Failed to cancel convictions',
          results: []
        };
      }
  
      return response;
    } catch (error: any) {
      this.logger.error(`Exception during conviction cancellation`, {
        error: error.message
      });
      
      return {
        success: false,
        errorMessage: error instanceof Error ? error.message : String(error || 'Conviction cancellation failed unexpectedly'),
        results: []
      };
    }
  }

  async submitConvictionsEncoded(submissionData: EncodedConvictionSubmissionRequest): Promise<BatchConvictionResponse> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Encoded conviction submission attempted without authentication');
      toastService.error('Cannot submit convictions: You are not logged in');
      
      return { 
        success: false, 
        errorMessage: 'Not authenticated',
        results: []
      };
    }

    if (!submissionData.convictions || !submissionData.convictions.trim()) {
      return {
        success: false,
        errorMessage: 'No encoded convictions provided',
        results: []
      };
    }

    const logContext = {
      convictionsLength: submissionData.convictions.length,
      hasResearchFile: !!submissionData.researchFile,
      hasNotes: !!submissionData.notes,
      researchFingerprintLength: submissionData.researchFile?.length
    };

    this.logger.info('Attempting to submit encoded convictions', logContext);

    try {
      const response = await this.convictionsApi.submitConvictionsEncoded(submissionData);

      if (response.success) {
        this.logger.info(`Encoded convictions submitted successfully`, {
          ...logContext,
          successCount: response.results.filter(r => r.success).length
        });
      } else {
        this.logger.warn(`Encoded conviction submission failed`, {
          ...logContext,
          error: response.errorMessage
        });
      }

      return response;
    } catch (error: any) {
      this.logger.error(`Exception during encoded conviction submission`, {
        ...logContext,
        error: error.message
      });
      
      return {
        success: false,
        errorMessage: error instanceof Error ? error.message : String(error || 'Encoded conviction submission failed unexpectedly'),
        results: []
      };
    }
  }

  async cancelConvictionsEncoded(cancellationData: EncodedConvictionCancellationRequest): Promise<BatchCancelResponse> {
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('Encoded conviction cancellation attempted without authentication');
      return { 
        success: false, 
        errorMessage: 'Not authenticated',
        results: []
      };
    }

    if (!cancellationData.convictionIds || !cancellationData.convictionIds.trim()) {
      return {
        success: false,
        errorMessage: 'No encoded conviction IDs provided',
        results: []
      };
    }

    const logContext = {
      convictionIdsLength: cancellationData.convictionIds.length,
      hasResearchFile: !!cancellationData.researchFile,
      hasNotes: !!cancellationData.notes,
      researchFingerprintLength: cancellationData.researchFile?.length
    };

    this.logger.info(`Attempting to cancel encoded convictions`, logContext);

    try {
      const response = await this.convictionsApi.cancelConvictionsEncoded(cancellationData);

      if (response.success) {
        this.logger.info(`Encoded convictions cancelled successfully`, logContext);
      } else {
        this.logger.warn(`Encoded conviction cancellation failed: ${response.errorMessage}`, logContext);
      }

      return response;
    } catch (error: any) {
      this.logger.error(`Exception during encoded conviction cancellation`, {
        ...logContext,
        error: error.message
      });
      
      return {
        success: false,
        errorMessage: error instanceof Error ? error.message : String(error || 'Encoded conviction cancellation failed unexpectedly'),
        results: []
      };
    }
  }
}