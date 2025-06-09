// frontend_dist/packages/config/src/index.ts

export interface AppConfig {
  // App identification
  appType: 'landing' | 'main';
  environment: 'development' | 'production' | 'staging';
  
  // API Configuration - KEEP OLD STRUCTURE
  apiBaseUrl: string;  // ✅ RESTORED - HTTP client expects this
  
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

function determineAppType(): 'landing' | 'main' {
  // Check if we're in landing app by looking at package.json name or environment
  if (process.env.REACT_APP_TYPE === 'landing') return 'landing';
  if (process.env.REACT_APP_TYPE === 'main') return 'main';
  
  // Fallback: check current URL or default
  if (typeof window !== 'undefined') {
    const currentPort = window.location.port;
    if (currentPort === '3001') return 'landing';
    if (currentPort === '3000') return 'main';
  }
  
  // Default based on process.env assumption
  return 'main';
}

function getConfig(): AppConfig {
  console.log('🔍 CONFIG: Loading unified configuration - START');
  console.log('🔍 CONFIG: process.env.REACT_APP_API_BASE_URL =', process.env.REACT_APP_API_BASE_URL);
  console.log('🔍 CONFIG: process.env.NODE_ENV =', process.env.NODE_ENV);
  console.log('🔍 CONFIG: process.env.REACT_APP_ENV =', process.env.REACT_APP_ENV);
  console.log('🔍 CONFIG: process.env.REACT_APP_TYPE =', process.env.REACT_APP_TYPE);

  const appType = determineAppType();
  const environment = (process.env.REACT_APP_ENV || process.env.NODE_ENV || 'development') as 'development' | 'production' | 'staging';

  console.log('🔍 CONFIG: appType =', appType);
  console.log('🔍 CONFIG: environment =', environment);

  // Determine API base URL - FIXED TO MATCH HTTP CLIENT EXPECTATIONS
  let apiBaseUrl: string;
  
  if (process.env.REACT_APP_API_BASE_URL) {
    apiBaseUrl = process.env.REACT_APP_API_BASE_URL;
    console.log('✅ CONFIG: Using REACT_APP_API_BASE_URL:', apiBaseUrl);
  } else if (environment === 'development') {
    apiBaseUrl = 'http://trading.local/api';
    console.log('✅ CONFIG: Using development default:', apiBaseUrl);
  } else {
    apiBaseUrl = `${window?.location?.protocol || 'https:'}//${window?.location?.hostname || 'api.digitaltrader.com'}/api`;
    console.log('✅ CONFIG: Using fallback URL:', apiBaseUrl);
  }

  // Determine WebSocket URL
  let wsUrl: string;
  if (process.env.REACT_APP_WS_URL) {
    wsUrl = process.env.REACT_APP_WS_URL;
  } else {
    const wsProtocol = apiBaseUrl.includes('https') ? 'wss:' : 'ws:';
    wsUrl = apiBaseUrl.replace(/^https?:/, wsProtocol).replace('/api', '/ws');
  }

  // Determine landing app URL
  let landingUrl: string;
  if (process.env.REACT_APP_LANDING_URL) {
    landingUrl = process.env.REACT_APP_LANDING_URL;
  } else if (environment === 'development') {
    landingUrl = 'http://localhost:3001';
  } else {
    landingUrl = 'https://digitaltrader.com';
  }

  // Determine main app URL  
  let mainAppUrl: string;
  if (process.env.REACT_APP_MAIN_APP_URL) {
    mainAppUrl = process.env.REACT_APP_MAIN_APP_URL;
  } else if (environment === 'development') {
    mainAppUrl = 'http://localhost:3000';
  } else {
    mainAppUrl = 'https://app.digitaltrader.com';
  }

  const config: AppConfig = {
    appType,
    environment,
    
    // ✅ RESTORED - HTTP client expects this exact property name
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
        simulator: `${mainAppUrl}/simulator`
      }
    },
    
    features: {
      enableLogs: process.env.REACT_APP_ENABLE_CONSOLE_LOGS === 'true' || environment === 'development',
      enableDebug: process.env.REACT_APP_ENABLE_DEBUG_MODE === 'true' || environment === 'development',
      autoRedirectValidCredentials: process.env.REACT_APP_AUTO_REDIRECT_VALID_CREDS !== 'false' // Default true
    },
    
    reconnection: {
      initialDelayMs: 1000,
      maxDelayMs: 30000,
      jitterFactor: 0.3,
      maxAttempts: 10
    }
  };

  console.log('🔍 CONFIG: Final API baseUrl:', config.apiBaseUrl);
  console.log('🔍 CONFIG: Full config object:', config);
  console.log('🔍 CONFIG: Loading unified configuration - END');
  
  return config;
}

// Export the config instance
export const config = getConfig();

// Export individual values for convenience - FIXED EXPORTS
export const APP_TYPE = config.appType;
export const API_BASE_URL = config.apiBaseUrl;  // ✅ RESTORED
export const WS_BASE_URL = config.websocket.url;
export const ENVIRONMENT = config.environment;
export const LANDING_URL = config.landing.baseUrl;
export const MAIN_APP_URL = config.main.baseUrl;

// Helper functions
export const isLandingApp = () => config.appType === 'landing';
export const isMainApp = () => config.appType === 'main';
export const isDevelopment = () => config.environment === 'development';
export const isProduction = () => config.environment === 'production';
export const shouldLog = () => config.features.enableLogs;
export const shouldDebug = () => config.features.enableDebug;

// Default export
export default config;