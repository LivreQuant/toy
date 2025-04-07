// src/config/index.ts

interface AppConfig {
    apiBaseUrl: string;
    wsBaseUrl: string;
    environment: 'development' | 'production' | 'test';
}

const getConfig = (): AppConfig => {
    const env = process.env.REACT_APP_ENV || process.env.NODE_ENV || 'development';
    const apiBaseUrl = process.env.REACT_APP_API_BASE_URL || 'http://trading.local/api';
    const wsBaseUrl = process.env.REACT_APP_WS_BASE_URL || 'ws://trading.local/ws';

    let config: AppConfig;
    switch (env) {
        case 'production':
            config = {
                apiBaseUrl: process.env.REACT_APP_API_BASE_URL || 'https://your-prod.com/api',
                wsBaseUrl: process.env.REACT_APP_WS_BASE_URL || 'wss://your-prod.com/ws',
                environment: 'production',
            };
            break;
        // Add other environments if needed (test, staging)
        default: // development
            config = {
                apiBaseUrl: apiBaseUrl,
                wsBaseUrl: wsBaseUrl,
                environment: 'development',
            };
            break;
    }
    console.log(`Configuration loaded for env: ${config.environment}`);
    return config;
};

// Ensure config is exported
export const config = getConfig();