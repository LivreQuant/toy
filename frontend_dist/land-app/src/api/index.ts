// landing-app/src/api/index.ts
import { HttpClient, AuthClient, LoginResponse } from '@trading-app/api';
import { TokenManager, DeviceIdManager, TokenData } from '@trading-app/auth';
import { LocalStorageService } from '@trading-app/storage';
import { environmentService } from '../config/environment';

/**
 * API service for landing app - with proper token storage flow
 */
class LandingApiService {
  private static instance: LandingApiService;
  private authApi: AuthClient | null = null;
  private tokenManager: TokenManager | null = null;
  private envService = environmentService;
  private initializationPromise: Promise<{ authApi: AuthClient; tokenManager: TokenManager }> | null = null;

  private constructor() {
    // Don't initialize immediately, do it lazily
  }

  public static getInstance(): LandingApiService {
    if (!LandingApiService.instance) {
      LandingApiService.instance = new LandingApiService();
    }
    return LandingApiService.instance;
  }

  private async createAuthServices(): Promise<{ authApi: AuthClient; tokenManager: TokenManager }> {
    try {
      // Create storage service first
      const storageService = new LocalStorageService();

      // Create device ID manager with storage service
      const deviceIdManager = DeviceIdManager.getInstance(storageService);

      // Create token manager
      const tokenManager = new TokenManager(storageService, deviceIdManager);

      // Create HTTP client
      let httpClient: HttpClient;
      
      try {
        httpClient = new HttpClient(tokenManager);
      } catch (error) {
        throw new Error(`HttpClient initialization failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }

      const authApi = new AuthClient(httpClient, tokenManager);

      if (this.envService.shouldLog()) {
        console.log('🔧 Landing API initialized successfully');
      }

      return { authApi, tokenManager };
    } catch (error) {
      console.error('❌ Failed to initialize landing API:', error);
      throw new Error(`Failed to initialize API service: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  public async getAuthServices(): Promise<{ authApi: AuthClient; tokenManager: TokenManager }> {
    if (this.authApi && this.tokenManager) {
      return { authApi: this.authApi, tokenManager: this.tokenManager };
    }

    if (this.initializationPromise) {
      return this.initializationPromise;
    }

    this.initializationPromise = this.createAuthServices();
    
    try {
      const services = await this.initializationPromise;
      this.authApi = services.authApi;
      this.tokenManager = services.tokenManager;
      return services;
    } catch (error) {
      this.initializationPromise = null; // Reset so we can try again
      throw error;
    }
  }

  public async getAuthApi(): Promise<AuthClient> {
    const { authApi } = await this.getAuthServices();
    return authApi;
  }

  public async getTokenManager(): Promise<TokenManager> {
    const { tokenManager } = await this.getAuthServices();
    return tokenManager;
  }

  /**
   * Login and ensure tokens are properly stored before returning
   */
  public async loginAndStoreTokens(username: string, password: string): Promise<LoginResponse & { tokensStored?: boolean }> {
    const { authApi, tokenManager } = await this.getAuthServices();
    
    if (this.envService.shouldLog()) {
      console.log("🔍 API: Starting login process for user:", username);
    }
    
    const response = await authApi.login(username, password);
    
    if (this.envService.shouldLog()) {
      console.log("🔍 API: Login response received:", {
        success: response.success,
        requiresVerification: response.requiresVerification,
        hasTokens: !!(response.accessToken && response.refreshToken)
      });
    }

    // If login successful and we have tokens, store them properly
    if (response.success && response.accessToken && response.refreshToken && response.expiresIn && response.userId) {
      if (this.envService.shouldLog()) {
        console.log("🔍 API: Storing tokens...");
      }

      const tokenData: TokenData = {
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        expiresAt: Date.now() + response.expiresIn * 1000,
        userId: response.userId,
      };

      // Store tokens and wait for completion
      await new Promise<void>((resolve, reject) => {
        try {
          tokenManager.storeTokens(tokenData);
          
          // Give localStorage time to write and verify storage
          setTimeout(() => {
            if (tokenManager.isAuthenticated() && tokenManager.getUserId() === response.userId) {
              if (this.envService.shouldLog()) {
                console.log("🔍 API: Token storage verified successfully");
              }
              resolve();
            } else {
              reject(new Error('Token storage verification failed'));
            }
          }, 150); // Increased buffer for reliable storage
        } catch (error) {
          reject(new Error(`Failed to store tokens: ${error}`));
        }
      });

      // Return response with confirmation that tokens are stored
      return { ...response, tokensStored: true };
    }

    // For other cases (verification required, failed login, etc.), return as-is
    return response;
  }

  public async healthCheck(): Promise<boolean> {
    try {
      const { authApi } = await this.getAuthServices();
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

// Export token manager getter
export const getTokenManager = () => landingApiService.getTokenManager();

// Export for debugging/health checks
export const getApiInfo = () => landingApiService.getApiInfo();