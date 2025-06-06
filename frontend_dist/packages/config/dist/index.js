// frontend_dist/packages/config/src/index.ts
function getConfig() {
    // Simple console logging instead of logger to avoid circular dependency
    console.log('🔍 CONFIG: Loading configuration');
    // Log all environment variables for debugging
    var envVars = {
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
    var apiBaseUrl;
    if (process.env.REACT_APP_API_BASE_URL) {
        apiBaseUrl = process.env.REACT_APP_API_BASE_URL;
        console.log('🔍 CONFIG: Using REACT_APP_API_BASE_URL', { apiBaseUrl: apiBaseUrl });
    }
    else if (process.env.NODE_ENV === 'development') {
        apiBaseUrl = 'http://trading.local';
        console.log('🔍 CONFIG: Development default API URL', { apiBaseUrl: apiBaseUrl });
    }
    else {
        // Production fallback
        if (typeof window !== 'undefined') {
            apiBaseUrl = "".concat(window.location.protocol, "//").concat(window.location.hostname);
            console.log('🔍 CONFIG: Production API URL from window.location', { apiBaseUrl: apiBaseUrl });
        }
        else {
            apiBaseUrl = 'http://trading.local';
            console.log('🔍 CONFIG: SSR fallback API URL', { apiBaseUrl: apiBaseUrl });
        }
    }
    // Determine WebSocket base URL
    var wsBaseUrl;
    if (process.env.REACT_APP_WS_URL) {
        wsBaseUrl = process.env.REACT_APP_WS_URL;
        console.log('🔍 CONFIG: Using REACT_APP_WS_URL', { wsBaseUrl: wsBaseUrl });
    }
    else {
        // Convert API URL to WebSocket URL
        wsBaseUrl = apiBaseUrl.replace(/^https?:/, apiBaseUrl.includes('https') ? 'wss:' : 'ws:') + '/ws';
        console.log('🔍 CONFIG: Derived WebSocket URL from API URL', { wsBaseUrl: wsBaseUrl });
    }
    var config = {
        apiBaseUrl: apiBaseUrl,
        wsBaseUrl: wsBaseUrl,
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
export var config = getConfig();
// Export individual values for convenience
export var API_BASE_URL = config.apiBaseUrl;
export var WS_BASE_URL = config.wsBaseUrl;
export var ENVIRONMENT = config.environment;
export var RECONNECTION_CONFIG = config.reconnection;
// Default export
export default config;
