// landing-app/src/api/index.ts
import { HttpClient, AuthClient } from '@trading-app/api';
import { TokenManager, DeviceIdManager } from '@trading-app/auth';
import { LocalStorageService } from '@trading-app/storage';
import { environmentService } from '../config/environment';

/**
 * API service for landing app - simplified and environment-aware
 */
class LandingApiService {
  private static instance: LandingApiService;
  private authApi: AuthClient;
  private envService = environmentService;

  private constructor() {
    this.authApi = this.createAuthClient();
  }

  public static getInstance(): LandingApiService {
    if (!LandingApiService.instance) {
      LandingApiService.instance = new LandingApiService();
    }
    return LandingApiService.instance;
  }

  private createAuthClient(): AuthClient {
    try {
      // Create storage service
      const storageService = new LocalStorageService();

      // Create device ID manager
      const deviceIdManager = DeviceIdManager.getInstance();

      // Create token manager with environment-aware configuration
      const tokenManager = new TokenManager(storageService, deviceIdManager);

      // Create HTTP client with API base URL from environment
      // Note: HttpClient might not accept configuration object as second parameter
      // Let's check what the actual HttpClient constructor expects
      const httpClient = new HttpClient(tokenManager);

      if (this.envService.shouldLog()) {
        console.log('🔧 Landing API initialized:', {
          apiUrl: this.envService.getApiConfig().baseUrl,
          environment: this.envService.getAppConfig().environment,
        });
      }

      return new AuthClient(httpClient, tokenManager);
    } catch (error) {
      console.error('❌ Failed to initialize landing API:', error);
      throw new Error('Failed to initialize API service');
    }
  }

  public getAuthApi(): AuthClient {
    return this.authApi;
  }

  /**
   * Health check for API connectivity
   */
  public async healthCheck(): Promise<boolean> {
    try {
      // Implement a simple health check if your API supports it
      // For now, just return true if the client was created successfully
      return !!this.authApi;
    } catch (error) {
      if (this.envService.shouldLog()) {
        console.error('❌ API health check failed:', error);
      }
      return false;
    }
  }

  /**
   * Get API configuration info for debugging
   */
  public getApiInfo() {
    return {
      baseUrl: this.envService.getApiConfig().baseUrl,
      environment: this.envService.getAppConfig().environment,
      isHealthy: this.healthCheck(), // This returns a Promise<boolean>
    };
  }
}

// Export singleton instance
export const landingApiService = LandingApiService.getInstance();

// Export auth API for convenience
export const authApi = landingApiService.getAuthApi();

// Export for debugging/health checks
export const getApiInfo = () => landingApiService.getApiInfo();