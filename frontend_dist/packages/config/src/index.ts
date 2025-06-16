// frontend_dist/packages/config/src/index.ts

export interface AppConfig {
  // App identification
  appType: 'land' | 'main' | 'book';
  environment: 'development' | 'production' | 'staging';
  
  // API Configuration
  apiBaseUrl: string;
  
  // WebSocket Configuration  
  websocket: {
    url: string;
  };
  
  // App URLs
  land: {
    baseUrl: string;
    routes: {
      home: string;
      signup: string;
      login: string;
      verifyEmail: string;
      forgotPassword: string;
      forgotUsername: string;
      resetPassword: string;
      enterpriseContact: string;
    };
  };
  
  main: {
    baseUrl: string;
    routes: {
      login: string;
      home: string;
      main: string;
      profile: string;
      books: string;
      simulator: string;
    };
  };

  book: {
    baseUrl: string;
    routes: {
      home: string;
      session: string;
    };
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
  
  // Fallback: check current URL
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const port = window.location.port;
    
    // Check subdomain-based detection
    if (hostname === 'trading.local' || hostname.includes('trading.local') && !hostname.includes('main.') && !hostname.includes('book.')) {
      return 'land';
    }
    if (hostname === 'main.trading.local' || hostname.includes('main.')) {
      return 'main';
    }
    if (hostname === 'book.trading.local' || hostname.includes('book.')) {
      return 'book';
    }
    
    // Port-based fallback for localhost development
    if (port === '3001') return 'land';
    if (port === '3000') return 'main';
    if (port === '3002') return 'book';
  }
  
  // Default assumption
  return 'main';
}

// Define the type for environment configs
type EnvironmentConfig = {
  land: string;
  main: string;
  book: string;
  api: string;
  ws: string;
};

type ConfigEnvironments = {
  development: EnvironmentConfig;
  production: EnvironmentConfig;
  staging: EnvironmentConfig;
};

function getEnvironmentUrls(environment: 'development' | 'production' | 'staging'): EnvironmentConfig {
  const configs: ConfigEnvironments = {
    development: {
      land: 'http://land.trading.local:3001',
      main: 'http://main.trading.local:3000',
      book: 'http://book.trading.local:3002',
      api: 'http://trading.local/api',
      ws: 'ws://trading.local/ws'
    },
    production: {
      land: 'https://land.trading.com',
      main: 'https://main.trading.com',
      book: 'https://book.trading.com',
      api: 'https://api.trading.com',
      ws: 'wss://api.trading.com/ws'
    },
    staging: {
      land: 'https://land-staging.trading.com',
      main: 'https://main-staging.trading.com', 
      book: 'https://book-staging.trading.com',
      api: 'https://api-staging.trading.com',
      ws: 'wss://api-staging.trading.com/ws'
    }
  };

  return configs[environment] || configs.development;
}

function getConfig(): AppConfig {
  console.log('🔍 CONFIG: Loading unified configuration - START');
  console.log('🔍 CONFIG: process.env.REACT_APP_API_BASE_URL =', process.env.REACT_APP_API_BASE_URL);
  console.log('🔍 CONFIG: process.env.NODE_ENV =', process.env.NODE_ENV);
  console.log('🔍 CONFIG: process.env.REACT_APP_ENV =', process.env.REACT_APP_ENV);
  console.log('🔍 CONFIG: process.env.REACT_APP_TYPE =', process.env.REACT_APP_TYPE);

  const appType = determineAppType();
  
  // Ensure environment is properly typed
  const envFromProcess = process.env.REACT_APP_ENV || process.env.NODE_ENV || 'development';
  const environment: 'development' | 'production' | 'staging' = 
    envFromProcess === 'production' ? 'production' :
    envFromProcess === 'staging' ? 'staging' : 'development';

  console.log('🔍 CONFIG: appType =', appType);
  console.log('🔍 CONFIG: environment =', environment);

  // Get environment-specific URLs
  const urls = getEnvironmentUrls(environment);

  // Allow environment variable overrides
  const apiBaseUrl = process.env.REACT_APP_API_BASE_URL || urls.api;
  const wsUrl = process.env.REACT_APP_WS_URL || urls.ws;
  const landAppUrl = process.env.REACT_APP_LAND_APP_URL || urls.land;
  const mainAppUrl = process.env.REACT_APP_MAIN_APP_URL || urls.main;
  const bookAppUrl = process.env.REACT_APP_BOOK_APP_URL || urls.book;

  const config: AppConfig = {
    appType,
    environment,
    
    apiBaseUrl: apiBaseUrl,
    
    websocket: {
      url: wsUrl
    },
    
    land: {
      baseUrl: landAppUrl,
      routes: {
        home: `${landAppUrl}/`,
        signup: `${landAppUrl}/signup`,
        login: `${mainAppUrl}/login`, // Land login redirects to main app
        verifyEmail: `${landAppUrl}/verify-email`,
        forgotPassword: `${landAppUrl}/forgot-password`,
        forgotUsername: `${landAppUrl}/forgot-username`,
        resetPassword: `${landAppUrl}/reset-password`,
        enterpriseContact: `${landAppUrl}/enterprise-contact`
      }
    },
    
    main: {
      baseUrl: mainAppUrl,
      routes: {
        login: `${mainAppUrl}/login`,
        home: `${mainAppUrl}/home`,
        main: `${mainAppUrl}/main`,
        profile: `${mainAppUrl}/profile`,
        books: `${bookAppUrl}/books`,
        simulator: `${bookAppUrl}/simulator`,
      }
    },

    book: {
      baseUrl: bookAppUrl,
      routes: {
        home: `${bookAppUrl}/`,
        session: `${bookAppUrl}/session`
      }
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

  console.log('🔍 CONFIG: Final configuration:', {
    appType: config.appType,
    environment: config.environment,
    apiBaseUrl: config.apiBaseUrl,
    wsUrl: config.websocket.url,
    landAppUrl: config.land.baseUrl,
    mainAppUrl: config.main.baseUrl,
    bookAppUrl: config.book.baseUrl,
  });
  console.log('🔍 CONFIG: Loading unified configuration - END');
  
  return config;
}

// Export the config instance
export const config = getConfig();

// Export individual values for convenience
export const APP_TYPE = config.appType;
export const API_BASE_URL = config.apiBaseUrl;
export const WS_BASE_URL = config.websocket.url;
export const ENVIRONMENT = config.environment;
export const LAND_APP_URL = config.land.baseUrl;
export const MAIN_APP_URL = config.main.baseUrl;
export const BOOK_APP_URL = config.book.baseUrl;

// Helper functions
export const isLandApp = () => config.appType === 'land';
export const isMainApp = () => config.appType === 'main';
export const isBookApp = () => config.appType === 'book';
export const isDevelopment = () => config.environment === 'development';
export const isProduction = () => config.environment === 'production';
export const shouldLog = () => config.features.enableLogs;
export const shouldDebug = () => config.features.enableDebug;

// Default export
export default config;