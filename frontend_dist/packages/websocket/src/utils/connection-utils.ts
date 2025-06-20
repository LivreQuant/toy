// frontend_dist/packages/websocket/src/utils/connection-utils.ts
import { getLogger } from '@trading-app/logging';
import { 
  connectionState, 
  authState, 
  simulatorState, 
  exchangeState, 
  portfolioState 
} from '@trading-app/state';
import { toastService } from '@trading-app/toast';
import { config } from '@trading-app/config';

import { StateManager, ToastService, ConfigService } from '../types/connection-types';

const logger = getLogger('ConnectionUtils');

/**
 * Implementation of StateManager that wraps the global state services
 */
export class GlobalStateManager implements StateManager {
  private logger = getLogger('GlobalStateManager');

  updateConnectionState(changes: any): void {
    this.logger.debug('Updating connection state', { changes });
    connectionState.updateState(changes);
  }

  updateSimulatorState(changes: any): void {
    this.logger.debug('Updating simulator state', { changes });
    simulatorState.updateState(changes);
  }

  updateExchangeState(changes: any): void {
    this.logger.debug('Updating exchange state', { changes });
    if (changes.symbols) {
      exchangeState.updateSymbols(changes.symbols);
    }
  }

  updatePortfolioState(changes: any): void {
    this.logger.debug('Updating portfolio state', { changes });
    portfolioState.updateState(changes);
  }

  getConnectionState(): any {
    return connectionState.getState();
  }

  getAuthState(): any {
    return authState.getState();
  }
}

/**
 * Implementation of ToastService that wraps the global toast service
 */
export class GlobalToastService implements ToastService {
  info(message: string, duration?: number, id?: string): void {
    toastService.info(message, duration, id);
  }

  warning(message: string, duration?: number, id?: string): void {
    toastService.warning(message, duration, id);
  }

  error(message: string, duration?: number, id?: string): void {
    toastService.error(message, duration, id);
  }

  success(message: string, duration?: number, id?: string): void {
    toastService.success(message, duration, id);
  }
}

/**
 * Implementation of ConfigService that wraps the global config
 */
export class GlobalConfigService implements ConfigService {
  getWebSocketUrl(): string {
    // Add comprehensive logging to debug the URL resolution
    logger.info('🔍 CONFIG DEBUG: Resolving WebSocket URL');
    
    // Log all environment variables related to websockets
    logger.info('🔍 CONFIG DEBUG: Environment variables', {
      NODE_ENV: process.env.NODE_ENV,
      REACT_APP_WS_URL: process.env.REACT_APP_WS_URL,
      REACT_APP_API_BASE_URL: process.env.REACT_APP_API_BASE_URL,
      REACT_APP_ENV: process.env.REACT_APP_ENV,
      location_hostname: typeof window !== 'undefined' ? window.location.hostname : 'server-side',
      location_port: typeof window !== 'undefined' ? window.location.port : 'server-side',
      location_protocol: typeof window !== 'undefined' ? window.location.protocol : 'server-side'
    });

    // Log the config object content
    logger.info('🔍 CONFIG DEBUG: Global config object', {
      config,
      hasWsBaseUrl: !!(config as any)?.wsBaseUrl,
      wsBaseUrl: (config as any)?.wsBaseUrl,
      configKeys: config ? Object.keys(config) : 'config is null/undefined'
    });
    
    let wsUrl: string;
    
    // PRIORITY 1: Environment variable (YOUR BACKEND)
    if (process.env.REACT_APP_WS_URL) {
      wsUrl = process.env.REACT_APP_WS_URL;
      logger.info('🔍 CONFIG DEBUG: Using REACT_APP_WS_URL (YOUR BACKEND)', { wsUrl });
    }
    // PRIORITY 2: Global config wsBaseUrl
    else if ((config as any)?.wsBaseUrl) {
      wsUrl = (config as any).wsBaseUrl;
      logger.info('🔍 CONFIG DEBUG: Using config.wsBaseUrl', { wsUrl });
    }
    // PRIORITY 3: Development default (YOUR BACKEND)
    else if (process.env.NODE_ENV === 'development') {
      wsUrl = 'ws://trading.local/ws';
      logger.info('🔍 CONFIG DEBUG: Development default - YOUR BACKEND', { wsUrl });
    }
    // PRIORITY 4: Production fallback
    else {
      if (typeof window !== 'undefined') {
        const hostname = window.location.hostname;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${protocol}//${hostname}/ws`;
        logger.info('🔍 CONFIG DEBUG: Production fallback', { wsUrl });
      } else {
        // Server-side rendering fallback
        wsUrl = 'ws://trading.local/ws';
        logger.info('🔍 CONFIG DEBUG: SSR fallback - YOUR BACKEND', { wsUrl });
      }
    }

    logger.info('🔍 CONFIG DEBUG: Final WebSocket URL resolved', { 
      finalUrl: wsUrl,
      source: 'getWebSocketUrl method'
    });

    logger.info('🚨 CRITICAL: React runs on localhost:3000, WebSocket connects to', { wsUrl });

    return wsUrl;
  }

  getReconnectionConfig(): {
    initialDelayMs: number;
    maxDelayMs: number;
    jitterFactor: number;
    maxAttempts: number;
  } {
    const reconnectionConfig = config?.reconnection || {
      initialDelayMs: 1000,
      maxDelayMs: 30000,
      jitterFactor: 0.3,
      maxAttempts: 10
    };
    
    logger.info('🔍 CONFIG DEBUG: Reconnection config', { reconnectionConfig });
    
    return reconnectionConfig;
  }
}

/**
 * Factory function to create a connection manager with global dependencies
 */
export function createConnectionManagerWithGlobalDeps() {
  return {
    stateManager: new GlobalStateManager(),
    toastService: new GlobalToastService(),
    configService: new GlobalConfigService()
  };
}