// frontend_dist/main-app/src/config/environment.ts
import { config, AppConfig } from '@trading-app/config';
import { getLogger } from '@trading-app/logging';

const logger = getLogger('Environment');

interface MainEnvironmentConfig extends AppConfig {
  // Main-specific additions can go here if needed
}

class MainEnvironmentService {
  private static instance: MainEnvironmentService;
  private config: MainEnvironmentConfig;

  private constructor() {
    // Use the unified config
    this.config = config as MainEnvironmentConfig;
    this.validateMainConfig();
  }

  public static getInstance(): MainEnvironmentService {
    if (!MainEnvironmentService.instance) {
      MainEnvironmentService.instance = new MainEnvironmentService();
    }
    return MainEnvironmentService.instance;
  }

  private validateMainConfig(): void {
    if (this.config.appType !== 'main') {
      console.warn('⚠️ Config indicates this is not a main app, but MainEnvironmentService is being used');
    }

    logger.info('🔧 Main App Environment initialized', {
      appType: this.config.appType,
      environment: this.config.environment,
      landingAppUrl: this.config.landing.baseUrl,
      mainAppUrl: this.config.main.baseUrl,
      apiBaseUrl: this.config.apiBaseUrl,
      wsUrl: this.config.websocket.url
    });
  }

  getLandingAppUrl(): string {
    return this.config.landing.baseUrl;
  }

  getMainAppUrl(): string {
    return this.config.main.baseUrl;
  }

  getApiBaseUrl(): string {
    return this.config.apiBaseUrl;
  }

  getWebSocketUrl(): string {
    return this.config.websocket.url;
  }

  getEnvironment(): string {
    return this.config.environment;
  }

  isDevelopment(): boolean {
    return this.config.environment === 'development';
  }

  isProduction(): boolean {
    return this.config.environment === 'production';
  }

  shouldLog(): boolean {
    return this.config.features.enableLogs;
  }
}

// Export singleton instance - fix the constructor access
export const environmentService = MainEnvironmentService.getInstance();