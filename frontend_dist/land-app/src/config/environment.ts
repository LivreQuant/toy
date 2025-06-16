// frontend_dist/land-app/src/config/environment.ts
import { config, AppConfig, getRoute } from '@trading-app/config';

interface LandEnvironmentConfig extends AppConfig {
  // Land-specific additions can go here if needed
}

class LandEnvironmentService {
  private static instance: LandEnvironmentService;
  private config: LandEnvironmentConfig;

  private constructor() {
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
      'apiBaseUrl',
      'gateway.baseUrl'
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
        gatewayUrl: this.config.gateway.baseUrl,
        apiUrl: this.config.apiBaseUrl,
        autoRedirectValidCredentials: this.config.features.autoRedirectValidCredentials,
        routes: this.config.gateway.routes
      });
    }
  }

  private getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  }

  public getConfig(): LandEnvironmentConfig {
    return { ...this.config };
  }

  public getGatewayUrl(): string {
    return this.config.gateway.baseUrl;
  }

  public getApiConfig() {
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

  // Route helper methods
  public getRoute(routeName: keyof typeof this.config.gateway.routes): string {
    return this.config.gateway.routes[routeName];
  }

  public getLoginUrl(): string {
    return this.getRoute('login');
  }

  public getDashboardUrl(): string {
    return this.getRoute('dashboard');
  }

  public getSignupUrl(): string {
    return this.getRoute('signup');
  }

  public getBooksUrl(): string {
    return this.getRoute('books');
  }

  public getSimulatorUrl(): string {
    return this.getRoute('simulator');
  }

  // Legacy compatibility methods for existing code
  public getMainAppUrl(): string {
    return this.config.gateway.baseUrl;
  }

  public getMainAppRoutes() {
    return {
      login: this.getRoute('login'),
      home: this.getRoute('dashboard'),
      main: this.getRoute('dashboard'),
      profile: this.getRoute('profile'),
      books: this.getRoute('books'),
      simulator: this.getRoute('simulator')
    };
  }

  public getLandAppConfig() {
    return {
      baseUrl: this.config.gateway.baseUrl,
      routes: {
        home: this.getRoute('home'),
        signup: this.getRoute('signup'),
        login: this.getRoute('login'),
        verifyEmail: this.getRoute('verifyEmail'),
        forgotPassword: this.getRoute('forgotPassword'),
        forgotUsername: this.getRoute('forgotUsername'),
        resetPassword: this.getRoute('resetPassword'),
        enterpriseContact: this.getRoute('enterpriseContact')
      }
    };
  }
}

// Export singleton instance
export const environmentService = LandEnvironmentService.getInstance();

// Export configuration object for direct access
export const landConfig = environmentService.getConfig();

// Export commonly used values for backward compatibility
export const mainAppRoutes = environmentService.getMainAppRoutes();
export const apiConfig = environmentService.getApiConfig();
export const wsConfig = environmentService.getWebSocketConfig();