// frontend_dist/packages/config/src/index.ts

export interface AppConfig {
  apiBaseUrl: string;
  wsBaseUrl: string;
  environment: string;
  reconnection: {
    initialDelayMs: number;
    maxDelayMs: number;
    jitterFactor: number;
    maxAttempts: number;
  };
}

function getConfig(): AppConfig {
  // Simple console logging instead of logger to avoid circular dependency
  console.log('🔍 CONFIG: Loading configuration');

  // Log all environment variables for debugging
  const envVars = {
    NODE_ENV: process.env.NODE_ENV,
    REACT_APP_API_BASE_URL: process.env.REACT_APP_API_BASE_URL,
    REACT_APP_WS_URL: process.env.REACT_APP_WS_URL,
    REACT_APP_ENV: process.env.REACT_APP_ENV,
    location: typeof window !== 'undefined' ? {
      hostname: window.location.hostname,
      port: window.location.port,
      protocol: window.location.protocol
    } : 'server-side'
  };

  console.log('🔍 CONFIG: Environment variables', envVars);

  // Determine API base URL
  let apiBaseUrl: string;
  if (process.env.REACT_APP_API_BASE_URL) {
    apiBaseUrl = process.env.REACT_APP_API_BASE_URL;
    console.log('🔍 CONFIG: Using REACT_APP_API_BASE_URL', { apiBaseUrl });
  } else if (process.env.NODE_ENV === 'development') {
    apiBaseUrl = 'http://trading.local';
    console.log('🔍 CONFIG: Development default API URL', { apiBaseUrl });
  } else {
    // Production fallback
    if (typeof window !== 'undefined') {
      apiBaseUrl = `${window.location.protocol}//${window.location.hostname}`;
      console.log('🔍 CONFIG: Production API URL from window.location', { apiBaseUrl });
    } else {
      apiBaseUrl = 'http://trading.local';
      console.log('🔍 CONFIG: SSR fallback API URL', { apiBaseUrl });
    }
  }

  // Determine WebSocket base URL
  let wsBaseUrl: string;
  if (process.env.REACT_APP_WS_URL) {
    wsBaseUrl = process.env.REACT_APP_WS_URL;
    console.log('🔍 CONFIG: Using REACT_APP_WS_URL', { wsBaseUrl });
  } else {
    // Convert API URL to WebSocket URL
    wsBaseUrl = apiBaseUrl.replace(/^https?:/, apiBaseUrl.includes('https') ? 'wss:' : 'ws:') + '/ws';
    console.log('🔍 CONFIG: Derived WebSocket URL from API URL', { wsBaseUrl });
  }

  const config: AppConfig = {
    apiBaseUrl,
    wsBaseUrl,
    environment: process.env.NODE_ENV || 'development',
    reconnection: {
      initialDelayMs: 1000,
      maxDelayMs: 30000,
      jitterFactor: 0.3,
      maxAttempts: 10
    }
  };

  console.log('🔍 CONFIG: Final configuration', config);
  
  return config;
}

// Export the config instance
export const config = getConfig();

// Export individual values for convenience
export const API_BASE_URL = config.apiBaseUrl;
export const WS_BASE_URL = config.wsBaseUrl;
export const ENVIRONMENT = config.environment;
export const RECONNECTION_CONFIG = config.reconnection;

// Default export
export default config;