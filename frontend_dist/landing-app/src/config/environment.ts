// frontend_dist/landing-app/src/config/environment.ts
import { config, AppConfig } from '@trading-app/config';

interface LandingEnvironmentConfig extends AppConfig {
  // Landing-specific additions can go here if needed
}

class LandingEnvironmentService {
  private static instance: LandingEnvironmentService;
  private config: LandingEnvironmentConfig;

  private constructor() {
    // Use the unified config
    this.config = config as LandingEnvironmentConfig;
    this.validateLandingConfig();
  }

  public static getInstance(): LandingEnvironmentService {
    if (!LandingEnvironmentService.instance) {
      LandingEnvironmentService.instance = new LandingEnvironmentService();
    }
    return LandingEnvironmentService.instance;
  }

  private validateLandingConfig(): void {
    if (this.config.appType !== 'landing') {
      console.warn('⚠️ Config indicates this is not a landing app, but LandingEnvironmentService is being used');
    }

    const requiredFields = [
      'api.baseUrl',
      'landing.baseUrl',
      'main.baseUrl'
    ];

    for (const field of requiredFields) {
      const value = this.getNestedValue(this.config, field);
      if (!value) {
        throw new Error(`Missing required configuration: ${field}`);
      }
    }

    if (this.shouldLog()) {
      console.log('🔧 Landing Environment Configuration Loaded:', {
        appType: this.config.appType,
        environment: this.config.environment,
        landingUrl: this.config.landing.baseUrl,
        mainAppUrl: this.config.main.baseUrl,
        apiUrl: this.config.api.baseUrl,
        autoRedirectValidCredentials: this.config.features.autoRedirectValidCredentials
      });
    }
  }

  private getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  }

  public getConfig(): LandingEnvironmentConfig {
    return { ...this.config };
  }

  public getMainAppUrl(): string {
    return this.config.main.baseUrl;
  }

  public getMainAppRoutes() {
    return { ...this.config.main.routes };
  }

  public getLandingConfig() {
    return { ...this.config.landing };
  }

  public getApiConfig() {
    return { ...this.config.api };
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
export const environmentService = LandingEnvironmentService.getInstance();

// Export configuration object for direct access
export const landingConfig = environmentService.getConfig();

// Export commonly used values
export const mainAppRoutes = environmentService.getMainAppRoutes();
export const apiConfig = environmentService.getApiConfig();
export const wsConfig = environmentService.getWebSocketConfig();