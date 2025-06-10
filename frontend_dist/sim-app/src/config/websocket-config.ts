// frontend_dist/main-app/src/config/websocket-config.ts
import { getLogger } from '@trading-app/logging';

const logger = getLogger('WebSocketConfig');

export interface WebSocketConfig {
  url: string;
  reconnection: {
    initialDelayMs: number;
    maxDelayMs: number;
    jitterFactor: number;
    maxAttempts: number;
  };
}

export function getWebSocketConfig(): WebSocketConfig {
  logger.info('🔍 WEBSOCKET CONFIG: Determining WebSocket configuration');
  
  // Log all relevant environment variables
  const envVars = {
    NODE_ENV: process.env.NODE_ENV,
    REACT_APP_WS_URL: process.env.REACT_APP_WS_URL,
    REACT_APP_API_BASE_URL: process.env.REACT_APP_API_BASE_URL,
    REACT_APP_ENV: process.env.REACT_APP_ENV,
    window_location: typeof window !== 'undefined' ? {
      hostname: window.location.hostname,
      port: window.location.port,
      protocol: window.location.protocol,
      href: window.location.href
    } : 'server-side'
  };
  
  logger.info('🔍 WEBSOCKET CONFIG: Environment variables', envVars);
  
  let wsUrl: string;
  
  // Priority order for WebSocket URL determination:
  // 1. REACT_APP_WS_URL environment variable (HIGHEST PRIORITY - YOUR BACKEND)
  // 2. Default to trading.local for development
  // 3. Production fallback
  
  if (process.env.REACT_APP_WS_URL) {
    wsUrl = process.env.REACT_APP_WS_URL;
    logger.info('🔍 WEBSOCKET CONFIG: Using REACT_APP_WS_URL (BACKEND)', { wsUrl });
  } else if (process.env.NODE_ENV === 'development') {
    // Development default - YOUR BACKEND
    wsUrl = 'ws://trading.local/ws';
    logger.info('🔍 WEBSOCKET CONFIG: Development default - YOUR BACKEND', { wsUrl });
  } else {
    // Production mode - derive from current location
    if (typeof window !== 'undefined') {
      const { protocol, hostname } = window.location;
      const wsProtocol = protocol === 'https:' ? 'wss:' : 'ws:';
      wsUrl = `${wsProtocol}//${hostname}/ws`;
      logger.info('🔍 WEBSOCKET CONFIG: Production mode - derived from location', { 
        location: window.location.href,
        wsUrl 
      });
    } else {
      // Server-side rendering fallback
      wsUrl = 'ws://trading.local/ws';
      logger.info('🔍 WEBSOCKET CONFIG: SSR fallback - YOUR BACKEND', { wsUrl });
    }
  }
  
  const config: WebSocketConfig = {
    url: wsUrl,
    reconnection: {
      initialDelayMs: 1000,
      maxDelayMs: 30000,
      jitterFactor: 0.3,
      maxAttempts: 10
    }
  };
  
  logger.info('🔍 WEBSOCKET CONFIG: Final configuration', config);
  logger.info('🚨 IMPORTANT: React app runs on localhost:3000, connects to WebSocket at', { wsUrl });
  
  return config;
}