// landing-app/src/config/environment.ts

interface EnvironmentConfig {
  mainApp: {
    baseUrl: string;
    routes: {
      login: string;
      signup: string;
      home: string;
      app: string;
      profile: string;
      books: string;
      simulator: string;
    };
  };
  api: {
    baseUrl: string;
  };
  websocket: {
    url: string;
  };
  landing: {
    baseUrl: string;
  };
  app: {
    environment: 'development' | 'production' | 'staging';
    enableLogs: boolean;
    enableDebug: boolean;
  };
}

class EnvironmentService {
  private static instance: EnvironmentService;
  private config: EnvironmentConfig;

  private constructor() {
    this.config = this.loadConfig();
    this.validateConfig();
  }

  public static getInstance(): EnvironmentService {
    if (!EnvironmentService.instance) {
      EnvironmentService.instance = new EnvironmentService();
    }
    return EnvironmentService.instance;
  }

  private loadConfig(): EnvironmentConfig {
    const env = process.env.REACT_APP_ENV || process.env.NODE_ENV || 'development';
    
    // Determine URLs based on environment
    const mainAppUrl = this.determineMainAppUrl();
    const apiBaseUrl = this.determineApiBaseUrl();
    const wsUrl = this.determineWebSocketUrl();
    const landingUrl = this.determineLandingUrl();

    return {
      mainApp: {
        baseUrl: mainAppUrl,
        routes: {
          login: `${mainAppUrl}/login`,
          signup: `${mainAppUrl}/signup`,
          home: `${mainAppUrl}/home`,
          app: `${mainAppUrl}/app`,
          profile: `${mainAppUrl}/profile`,
          books: `${mainAppUrl}/books`,
          simulator: `${mainAppUrl}/simulator`,
        },
      },
      api: {
        baseUrl: apiBaseUrl,
      },
      websocket: {
        url: wsUrl,
      },
      landing: {
        baseUrl: landingUrl,
      },
      app: {
        environment: env as 'development' | 'production' | 'staging',
        enableLogs: process.env.REACT_APP_ENABLE_CONSOLE_LOGS === 'true',
        enableDebug: process.env.REACT_APP_ENABLE_DEBUG_MODE === 'true',
      },
    };
  }

  private determineMainAppUrl(): string {
    if (process.env.REACT_APP_MAIN_APP_URL) {
      return process.env.REACT_APP_MAIN_APP_URL;
    }

    if (process.env.NODE_ENV === 'production' && process.env.REACT_APP_MAIN_APP_PRODUCTION_URL) {
      return process.env.REACT_APP_MAIN_APP_PRODUCTION_URL;
    }

    return 'http://localhost:3000';
  }

  private determineApiBaseUrl(): string {
    if (process.env.REACT_APP_API_BASE_URL) {
      return process.env.REACT_APP_API_BASE_URL;
    }

    if (process.env.NODE_ENV === 'production' && process.env.REACT_APP_API_PRODUCTION_URL) {
      return process.env.REACT_APP_API_PRODUCTION_URL;
    }

    return 'http://localhost:8080/api';
  }

  private determineWebSocketUrl(): string {
    if (process.env.REACT_APP_WS_URL) {
      return process.env.REACT_APP_WS_URL;
    }

    if (process.env.NODE_ENV === 'production' && process.env.REACT_APP_WS_PRODUCTION_URL) {
      return process.env.REACT_APP_WS_PRODUCTION_URL;
    }

    return 'ws://localhost:8080/ws';
  }

  private determineLandingUrl(): string {
    if (process.env.REACT_APP_LANDING_URL) {
      return process.env.REACT_APP_LANDING_URL;
    }

    if (process.env.NODE_ENV === 'production' && process.env.REACT_APP_LANDING_PRODUCTION_URL) {
      return process.env.REACT_APP_LANDING_PRODUCTION_URL;
    }

    return 'http://localhost:3001';
  }

  private validateConfig(): void {
    const requiredFields = [
      'mainApp.baseUrl',
      'api.baseUrl',
      'landing.baseUrl'
    ];

    for (const field of requiredFields) {
      const value = this.getNestedValue(this.config, field);
      if (!value) {
        throw new Error(`Missing required configuration: ${field}`);
      }
    }

    if (this.config.app.enableLogs) {
      console.log('🔧 Environment Configuration Loaded:', {
        environment: this.config.app.environment,
        mainAppUrl: this.config.mainApp.baseUrl,
        apiUrl: this.config.api.baseUrl,
        landingUrl: this.config.landing.baseUrl,
      });
    }
  }

  private getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  }

  public getConfig(): EnvironmentConfig {
    return { ...this.config };
  }

  public getMainAppUrl(): string {
    return this.config.mainApp.baseUrl;
  }

  public getMainAppRoutes() {
    return { ...this.config.mainApp.routes };
  }

  public getApiConfig() {
    return { ...this.config.api };
  }

  public getWebSocketConfig() {
    return { ...this.config.websocket };
  }

  public getLandingConfig() {
    return { ...this.config.landing };
  }

  public getAppConfig() {
    return { ...this.config.app };
  }

  public isProduction(): boolean {
    return this.config.app.environment === 'production';
  }

  public isDevelopment(): boolean {
    return this.config.app.environment === 'development';
  }

  public shouldLog(): boolean {
    return this.config.app.enableLogs;
  }

  public shouldDebug(): boolean {
    return this.config.app.enableDebug;
  }
}

// Export singleton instance
export const environmentService = EnvironmentService.getInstance();

// Export configuration object for direct access
export const config = environmentService.getConfig();

// Export commonly used values
export const mainAppRoutes = environmentService.getMainAppRoutes();
export const apiConfig = environmentService.getApiConfig();
export const wsConfig = environmentService.getWebSocketConfig();