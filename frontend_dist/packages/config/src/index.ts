// frontend_dist/packages/config/src/index.ts

export interface AppConfig {
  // App identification
  appType: 'land' | 'main' | 'book';
  environment: 'development' | 'production' | 'staging';
  
  // Gateway Configuration - single entry point
  gateway: {
    baseUrl: string;
    routes: {
      // Landing app routes
      home: string;
      signup: string;
      verifyEmail: string;
      forgotPassword: string;
      forgotUsername: string;
      resetPassword: string;
      enterpriseContact: string;
      
      // Main app routes
      login: string;
      dashboard: string;
      profile: string;
      
      // Book app routes
      books: string;
      simulator: string;
    };
  };
  
  // API Configuration
  apiBaseUrl: string;
  
  // WebSocket Configuration  
  websocket: {
    url: string;
  };
  
  // Feature flags
  features: {
    enableLogs: boolean;
    enableDebug: boolean;
    autoRedirectValidCredentials: boolean;
  };
  
  // Reconnection config
  reconnection: {
    initialDelayMs: number;
    maxDelayMs: number;
    jitterFactor: number;
    maxAttempts: number;
  };
}

function determineAppType(): 'land' | 'main' | 'book' {
  // Check environment variable first
  if (process.env.REACT_APP_TYPE === 'land') return 'land';
  if (process.env.REACT_APP_TYPE === 'main') return 'main';
  if (process.env.REACT_APP_TYPE === 'book') return 'book';
  
  // Fallback: check current path since we're always behind gateway
  if (typeof window !== 'undefined') {
    const path = window.location.pathname;
    
    // ENTIRE main app is behind /app
    if (path.startsWith('/app')) {
      return 'main';
    }
    // Book app routes
    if (path.startsWith('/books') || path.startsWith('/simulator')) {
      return 'book';
    }
    // Everything else (/, /signup, /login, etc.) is landing app
    return 'land';
  }
  
  // Default assumption
  return 'land';
}

function getGatewayUrls(environment: 'development' | 'production' | 'staging'): string {
  const gateways = {
    development: 'http://localhost:8081',
    production: 'https://app.digitaltrader.com',
    staging: 'https://app-staging.digitaltrader.com'
  };

  return gateways[environment] || gateways.development;
}

function getConfig(): AppConfig {
  console.log('🔍 CONFIG: Loading gateway-first configuration - START');

  const appType = determineAppType();
  
  // Ensure environment is properly typed
  const envFromProcess = process.env.REACT_APP_ENV || process.env.NODE_ENV || 'development';
  const environment: 'development' | 'production' | 'staging' = 
    envFromProcess === 'production' ? 'production' :
    envFromProcess === 'staging' ? 'staging' : 'development';

  console.log('🔍 CONFIG: appType =', appType);
  console.log('🔍 CONFIG: environment =', environment);

  // Get gateway URL
  const gatewayBaseUrl = process.env.REACT_APP_GATEWAY_URL || getGatewayUrls(environment);

  // API and WebSocket URLs
  const apiBaseUrl = process.env.REACT_APP_API_BASE_URL || 
    (environment === 'production' ? 'https://api.digitaltrader.com' : 'http://trading.local/api');
  
  const wsUrl = process.env.REACT_APP_WS_URL || 
    (environment === 'production' ? 'wss://api.digitaltrader.com/ws' : 'ws://trading.local/ws');

  const config: AppConfig = {
    appType,
    environment,
    
    gateway: {
      baseUrl: gatewayBaseUrl,
      routes: {
        // Landing app routes (served at root)
        home: `${gatewayBaseUrl}/`,
        signup: `${gatewayBaseUrl}/signup`,
        verifyEmail: `${gatewayBaseUrl}/verify-email`,
        forgotPassword: `${gatewayBaseUrl}/forgot-password`,
        forgotUsername: `${gatewayBaseUrl}/forgot-username`,
        resetPassword: `${gatewayBaseUrl}/reset-password`,
        enterpriseContact: `${gatewayBaseUrl}/enterprise-contact`,
        
        // Main app routes - ALL UNDER /app
        login: `${gatewayBaseUrl}/app/login`,
        dashboard: `${gatewayBaseUrl}/app/home`,  // Main dashboard at /app/home
        profile: `${gatewayBaseUrl}/app/profile`,
        
        // Book app routes
        books: `${gatewayBaseUrl}/books`,
        simulator: `${gatewayBaseUrl}/simulator`,
      }
    },
    
    apiBaseUrl,
    
    websocket: {
      url: wsUrl
    },
    
    features: {
      enableLogs: process.env.REACT_APP_ENABLE_CONSOLE_LOGS === 'true' || environment === 'development',
      enableDebug: process.env.REACT_APP_ENABLE_DEBUG_MODE === 'true' || environment === 'development',
      autoRedirectValidCredentials: process.env.REACT_APP_AUTO_REDIRECT_VALID_CREDS !== 'false'
    },
    
    reconnection: {
      initialDelayMs: 1000,
      maxDelayMs: 30000,
      jitterFactor: 0.3,
      maxAttempts: 10
    }
  };

  console.log('🔍 CONFIG: Final gateway configuration:', {
    appType: config.appType,
    environment: config.environment,
    gatewayBaseUrl: config.gateway.baseUrl,
    apiBaseUrl: config.apiBaseUrl,
    wsUrl: config.websocket.url,
    sampleRoutes: {
      home: config.gateway.routes.home,        // /
      login: config.gateway.routes.login,      // /app/login
      dashboard: config.gateway.routes.dashboard, // /app/home
      books: config.gateway.routes.books       // /books
    }
  });
  console.log('🔍 CONFIG: Loading gateway-first configuration - END');
  
  return config;
}

// Export the config instance
export const config = getConfig();

// Export individual values for convenience
export const APP_TYPE = config.appType;
export const GATEWAY_URL = config.gateway.baseUrl;
export const API_BASE_URL = config.apiBaseUrl;
export const WS_BASE_URL = config.websocket.url;
export const ENVIRONMENT = config.environment;

// Helper functions
export const isLandApp = () => config.appType === 'land';
export const isMainApp = () => config.appType === 'main';
export const isBookApp = () => config.appType === 'book';
export const isDevelopment = () => config.environment === 'development';
export const isProduction = () => config.environment === 'production';
export const shouldLog = () => config.features.enableLogs;
export const shouldDebug = () => config.features.enableDebug;

// Route helpers
export const getRoute = (routeName: keyof typeof config.gateway.routes) => config.gateway.routes[routeName];
export const getAllRoutes = () => ({ ...config.gateway.routes });

// Default export
export default config;