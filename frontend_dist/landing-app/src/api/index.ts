// landing-app/src/api/index.ts
import { HttpClient, AuthClient } from '@trading-app/api';
import { TokenManager, DeviceIdManager } from '@trading-app/auth';
import { LocalStorageService } from '@trading-app/storage';
import { environmentService } from '../config/environment';

/**
 * API service for landing app - lazy initialization approach
 */
class LandingApiService {
  private static instance: LandingApiService;
  private authApi: AuthClient | null = null;
  private envService = environmentService;
  private initializationPromise: Promise<AuthClient> | null = null;

  private constructor() {
    // Don't initialize immediately, do it lazily
  }

  public static getInstance(): LandingApiService {
    if (!LandingApiService.instance) {
      LandingApiService.instance = new LandingApiService();
    }
    return LandingApiService.instance;
  }

  private async createAuthClient(): Promise<AuthClient> {
    try {
      // Create storage service first
      const storageService = new LocalStorageService();

      // Create device ID manager with storage service
      const deviceIdManager = DeviceIdManager.getInstance(storageService);

      // Create token manager
      const tokenManager = new TokenManager(storageService, deviceIdManager);

      // Try different HttpClient constructor patterns
      let httpClient: HttpClient;
      
      try {
        // Most likely pattern - just TokenManager
        httpClient = new HttpClient(tokenManager);
      } catch (error) {
        throw new Error(`HttpClient initialization failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }

      if (this.envService.shouldLog()) {
        console.log('🔧 Landing API initialized successfully');
      }

      return new AuthClient(httpClient, tokenManager);
    } catch (error) {
      console.error('❌ Failed to initialize landing API:', error);
      throw new Error(`Failed to initialize API service: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  public async getAuthApi(): Promise<AuthClient> {
    if (this.authApi) {
      return this.authApi;
    }

    if (this.initializationPromise) {
      return this.initializationPromise;
    }

    this.initializationPromise = this.createAuthClient();
    
    try {
      this.authApi = await this.initializationPromise;
      return this.authApi;
    } catch (error) {
      this.initializationPromise = null; // Reset so we can try again
      throw error;
    }
  }

  public async healthCheck(): Promise<boolean> {
    try {
      const authApi = await this.getAuthApi();
      return !!(authApi && typeof authApi.login === 'function');
    } catch (error) {
      if (this.envService.shouldLog()) {
        console.error('❌ API health check failed:', error);
      }
      return false;
    }
  }

  public getApiInfo() {
    return {
      baseUrl: this.envService.getApiConfig().baseUrl,
      environment: this.envService.getAppConfig().environment,
      isHealthy: this.healthCheck(),
    };
  }
}

// Export singleton instance
export const landingApiService = LandingApiService.getInstance();

// Export auth API getter (now async)
export const getAuthApi = () => landingApiService.getAuthApi();

// Export for debugging/health checks
export const getApiInfo = () => landingApiService.getApiInfo();