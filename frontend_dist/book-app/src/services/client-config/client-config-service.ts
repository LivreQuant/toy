// frontend_dist/book-app/src/services/client-config/client-config-service.ts
import { getLogger } from '@trading-app/logging';
import { BookClient } from '@trading-app/api';
import { TokenManager } from '@trading-app/auth';

export interface ClientConfigResponse {
  config: string | null;
  success: boolean;
  error?: string;
}

export class ClientConfigService {
  private static instance: ClientConfigService;
  private logger = getLogger('ClientConfigService');
  private bookClient: BookClient;
  private tokenManager: TokenManager;

  private constructor(bookClient: BookClient, tokenManager: TokenManager) {
    this.bookClient = bookClient;
    this.tokenManager = tokenManager;
  }

  static getInstance(bookClient?: BookClient, tokenManager?: TokenManager): ClientConfigService {
    if (!ClientConfigService.instance) {
      if (!bookClient || !tokenManager) {
        throw new Error('ClientConfigService requires BookClient and TokenManager for initialization');
      }
      ClientConfigService.instance = new ClientConfigService(bookClient, tokenManager);
    }
    return ClientConfigService.instance;
  }

  async getClientConfig(bookId: string): Promise<ClientConfigResponse> {
    if (!this.tokenManager.isAuthenticated()) {
      return {
        config: null,
        success: false,
        error: 'Not authenticated'
      };
    }

    try {
      this.logger.info(`[ClientConfigService] Loading config for book: ${bookId}`);
      const response = await this.bookClient.getClientConfig(bookId);
      
      if (response.success) {
        this.logger.info(`[ClientConfigService] Config loaded successfully for book: ${bookId}`, {
          hasConfig: !!response.config,
          configLength: response.config?.length || 0
        });
        
        return {
          config: response.config || null,
          success: true
        };
      } else {
        this.logger.warn(`[ClientConfigService] Failed to load config for book: ${bookId}`, {
          error: response.error
        });
        
        return {
          config: null,
          success: false,
          error: response.error || 'Failed to load client config'
        };
      }
    } catch (error: any) {
      this.logger.error(`[ClientConfigService] Error loading config for book: ${bookId}`, {
        error: error.message
      });
      
      return {
        config: null,
        success: false,
        error: error.message || 'Unknown error loading client config'
      };
    }
  }

  async storeClientConfig(bookId: string, config: string): Promise<boolean> {
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.warn('[ClientConfigService] Cannot store config: not authenticated');
      return false;
    }

    try {
      this.logger.info(`[ClientConfigService] Storing config for book: ${bookId}`, {
        configLength: config.length
      });
      
      const response = await this.bookClient.updateClientConfig(bookId, config);
      
      if (response.success) {
        this.logger.info(`[ClientConfigService] Config stored successfully for book: ${bookId}`);
        return true;
      } else {
        this.logger.warn(`[ClientConfigService] Failed to store config for book: ${bookId}`, {
          error: response.error
        });
        return false;
      }
    } catch (error: any) {
      this.logger.error(`[ClientConfigService] Error storing config for book: ${bookId}`, {
        error: error.message
      });
      return false;
    }
  }
}