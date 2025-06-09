// frontend_dist/main-app/src/config/environment.ts
import { getLogger } from '@trading-app/logging';

const logger = getLogger('Environment');

class EnvironmentService {
  private landingAppUrl: string;
  private mainAppUrl: string;
  private apiBaseUrl: string;
  private wsUrl: string;
  private environment: string;

  constructor() {
    this.environment = process.env.REACT_APP_ENV || 'development';
    
    // Landing app URL
    this.landingAppUrl = process.env.REACT_APP_LANDING_URL || 'http://localhost:3001';
    
    // Main app URL  
    this.mainAppUrl = process.env.REACT_APP_MAIN_APP_URL || 'http://localhost:3000';
    
    // API URLs
    this.apiBaseUrl = process.env.REACT_APP_API_BASE_URL || 'http://trading.local/api';
    this.wsUrl = process.env.REACT_APP_WS_URL || 'ws://trading.local/ws';

    logger.info('🔧 Main App Environment initialized', {
      environment: this.environment,
      landingAppUrl: this.landingAppUrl,
      mainAppUrl: this.mainAppUrl,
      apiBaseUrl: this.apiBaseUrl,
      wsUrl: this.wsUrl
    });
  }

  getLandingAppUrl(): string {
    return this.landingAppUrl;
  }

  getMainAppUrl(): string {
    return this.mainAppUrl;
  }

  getApiBaseUrl(): string {
    return this.apiBaseUrl;
  }

  getWebSocketUrl(): string {
    return this.wsUrl;
  }

  getEnvironment(): string {
    return this.environment;
  }

  isDevelopment(): boolean {
    return this.environment === 'development';
  }

  isProduction(): boolean {
    return this.environment === 'production';
  }

  shouldLog(): boolean {
    return this.isDevelopment();
  }
}

// Export singleton instance
export const environmentService = new EnvironmentService();