// frontend_dist/land-app/src/config/environment.ts
import { config, AppConfig } from '@trading-app/config';

interface LandEnvironmentConfig extends AppConfig {
  // Land-specific additions can go here if needed
}

class LandEnvironmentService {
  private static instance: LandEnvironmentService;
  private config: LandEnvironmentConfig;

  private constructor() {
    // Use the unified config
    this.config = config as LandEnvironmentConfig;
    this.validateLandConfig();
  }

  public static getInstance(): LandEnvironmentService {
    if (!LandEnvironmentService.instance) {
      LandEnvironmentService.instance = new LandEnvironmentService();
    }
    return LandEnvironmentService.instance;
  }

  private validateLandConfig(): void {
    if (this.config.appType !== 'land') {
      console.warn('⚠️ Config indicates this is not a land app, but LandEnvironmentService is being used');
    }

    const requiredFields = [
      'apiBaseUrl',  // ✅ FIXED: Use top-level apiBaseUrl instead of api.baseUrl
      'land.baseUrl',
      'main.baseUrl'
    ];

    for (const field of requiredFields) {
      const value = this.getNestedValue(this.config, field);
      if (!value) {
        throw new Error(`Missing required configuration: ${field}`);
      }
    }

    if (this.shouldLog()) {
      console.log('🔧 Land Environment Configuration Loaded:', {
        appType: this.config.appType,
        environment: this.config.environment,
        landAppUrl: this.config.land.baseUrl,
        mainAppUrl: this.config.main.baseUrl,
        apiUrl: this.config.apiBaseUrl,  // ✅ FIXED: Use apiBaseUrl
        autoRedirectValidCredentials: this.config.features.autoRedirectValidCredentials
      });
    }
  }

  private getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  }

  public getConfig(): LandEnvironmentConfig {
    return { ...this.config };
  }

  public getMainAppUrl(): string {
    return this.config.main.baseUrl;
  }

  public getMainAppRoutes() {
    return { ...this.config.main.routes };
  }

  public getLandAppConfig() {
    return { ...this.config.land };
  }

  public getApiConfig() {
    // ✅ FIXED: Return object with baseUrl property from top-level apiBaseUrl
    return { 
      baseUrl: this.config.apiBaseUrl 
    };
  }

  public getWebSocketConfig() {
    return { ...this.config.websocket };
  }

  public getAppConfig() {
    return {
      appType: this.config.appType,
      environment: this.config.environment,
      enableLogs: this.config.features.enableLogs,
      enableDebug: this.config.features.enableDebug
    };
  }

  public getFeatures() {
    return { ...this.config.features };
  }

  public isProduction(): boolean {
    return this.config.environment === 'production';
  }

  public isDevelopment(): boolean {
    return this.config.environment === 'development';
  }

  public shouldLog(): boolean {
    return this.config.features.enableLogs;
  }

  public shouldDebug(): boolean {
    return this.config.features.enableDebug;
  }

  public shouldAutoRedirectValidCredentials(): boolean {
    return this.config.features.autoRedirectValidCredentials;
  }
}

// Export singleton instance
export const environmentService = LandEnvironmentService.getInstance();

// Export configuration object for direct access
export const landConfig = environmentService.getConfig();

// Export commonly used values
export const mainAppRoutes = environmentService.getMainAppRoutes();
export const apiConfig = environmentService.getApiConfig();
export const wsConfig = environmentService.getWebSocketConfig();