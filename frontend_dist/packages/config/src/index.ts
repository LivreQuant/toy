// frontend_dist/packages/config/src/index.ts

export interface AppConfig {
  // App identification
  appType: 'landing' | 'main' | 'simulator';
  environment: 'development' | 'production' | 'staging';
  
  // API Configuration
  apiBaseUrl: string;
  
  // WebSocket Configuration  
  websocket: {
    url: string;
  };
  
  // App URLs
  landing: {
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
      app: string;
      profile: string;
      books: string;
      simulator: string;
    };
  };

  simulator: {
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

function determineAppType(): 'landing' | 'main' | 'simulator' {
  // Check environment variable first
  if (process.env.REACT_APP_TYPE === 'landing') return 'landing';
  if (process.env.REACT_APP_TYPE === 'main') return 'main';
  if (process.env.REACT_APP_TYPE === 'simulator') return 'simulator';
  
  // Fallback: check current URL
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const port = window.location.port;
    
    // Check subdomain-based detection
    if (hostname === 'trading.local' || hostname.includes('trading.local') && !hostname.includes('app.') && !hostname.includes('sim.')) {
      return 'landing';
    }
    if (hostname === 'app.trading.local' || hostname.includes('app.')) {
      return 'main';
    }
    if (hostname === 'sim.trading.local' || hostname.includes('sim.')) {
      return 'simulator';
    }
    
    // Port-based fallback for localhost development
    if (port === '3001') return 'landing';
    if (port === '3000') return 'main';
    if (port === '3002') return 'simulator';
  }
  
  // Default assumption
  return 'main';
}

// Define the type for environment configs
type EnvironmentConfig = {
  landing: string;
  main: string;
  simulator: string;
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
      landing: 'http://trading.local:3001',
      main: 'http://app.trading.local:3000',
      simulator: 'http://sim.trading.local:3002',
      api: 'http://trading.local/api',
      ws: 'ws://trading.local/ws'
    },
    production: {
      landing: 'https://trading.com',
      main: 'https://app.trading.com',
      simulator: 'https://sim.trading.com',
      api: 'https://api.trading.com',
      ws: 'wss://api.trading.com/ws'
    },
    staging: {
      landing: 'https://staging.trading.com',
      main: 'https://app-staging.trading.com', 
      simulator: 'https://sim-staging.trading.com',
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
  const landingUrl = process.env.REACT_APP_LANDING_URL || urls.landing;
  const mainAppUrl = process.env.REACT_APP_MAIN_APP_URL || urls.main;
  const simulatorUrl = process.env.REACT_APP_SIMULATOR_URL || urls.simulator;

  const config: AppConfig = {
    appType,
    environment,
    
    apiBaseUrl: apiBaseUrl,
    
    websocket: {
      url: wsUrl
    },
    
    landing: {
      baseUrl: landingUrl,
      routes: {
        home: `${landingUrl}/`,
        signup: `${landingUrl}/signup`,
        login: `${mainAppUrl}/login`, // Landing login redirects to main app
        verifyEmail: `${landingUrl}/verify-email`,
        forgotPassword: `${landingUrl}/forgot-password`,
        forgotUsername: `${landingUrl}/forgot-username`,
        resetPassword: `${landingUrl}/reset-password`,
        enterpriseContact: `${landingUrl}/enterprise-contact`
      }
    },
    
    main: {
      baseUrl: mainAppUrl,
      routes: {
        login: `${mainAppUrl}/login`,
        home: `${mainAppUrl}/home`,
        app: `${mainAppUrl}/app`,
        profile: `${mainAppUrl}/profile`,
        books: `${mainAppUrl}/books`,
        simulator: `${simulatorUrl}` // Cross-reference to simulator app
      }
    },

    simulator: {
      baseUrl: simulatorUrl,
      routes: {
        home: `${simulatorUrl}/`,
        session: `${simulatorUrl}/session`
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
    landingUrl: config.landing.baseUrl,
    mainAppUrl: config.main.baseUrl,
    simulatorUrl: config.simulator.baseUrl
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
export const LANDING_URL = config.landing.baseUrl;
export const MAIN_APP_URL = config.main.baseUrl;
export const SIMULATOR_URL = config.simulator.baseUrl;

// Helper functions
export const isLandingApp = () => config.appType === 'landing';
export const isMainApp = () => config.appType === 'main';
export const isSimulatorApp = () => config.appType === 'simulator';
export const isDevelopment = () => config.environment === 'development';
export const isProduction = () => config.environment === 'production';
export const shouldLog = () => config.features.enableLogs;
export const shouldDebug = () => config.features.enableDebug;

// Default export
export default config;