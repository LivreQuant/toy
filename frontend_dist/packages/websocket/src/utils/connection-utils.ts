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
import { TokenManager } from '@trading-app/auth'; // ADD THIS IMPORT

import { StateManager, ToastService, ConfigService } from '../types/connection-types';

const logger = getLogger('ConnectionUtils');

/**
 * ENHANCED GlobalStateManager with comprehensive logging for data flow tracing
 */
export class GlobalStateManager implements StateManager {
  private logger = getLogger('GlobalStateManager');

  constructor() {
    this.logger.info('🌐 GLOBAL_STATE: GlobalStateManager initialized');
  }

  updateConnectionState(changes: any): void {
    this.logger.debug('🌐 GLOBAL_STATE: Updating connection state', { changes });
    connectionState.updateState(changes);
    this.logger.debug('🌐 GLOBAL_STATE: Connection state update complete');
  }

  updateSimulatorState(changes: any): void {
    this.logger.debug('🌐 GLOBAL_STATE: Updating simulator state', { changes });
    simulatorState.updateState(changes);
    this.logger.debug('🌐 GLOBAL_STATE: Simulator state update complete');
  }

  updateExchangeState(changes: any): void {
    this.logger.debug('🌐 GLOBAL_STATE: Updating exchange state', { changes });
    if (changes.symbols) {
      this.logger.info('🌐 GLOBAL_STATE: Updating legacy symbols format', {
        symbolCount: Object.keys(changes.symbols).length
      });
      exchangeState.updateSymbols(changes.symbols);
    }
    this.logger.debug('🌐 GLOBAL_STATE: Exchange state update complete');
  }

  updatePortfolioState(changes: any): void {
    this.logger.debug('🌐 GLOBAL_STATE: Updating portfolio state', { changes });
    portfolioState.updateState(changes);
    this.logger.debug('🌐 GLOBAL_STATE: Portfolio state update complete');
  }

  // CRITICAL: These methods ensure WebSocket exchange data flows to global state
  updateEquityData(data: any[]): void {
    this.logger.info('🌐 GLOBAL_STATE: EQUITY UPDATE START', { 
      dataCount: data.length,
      sampleSymbols: data.slice(0, 3).map(e => e.symbol),
      samplePrices: data.slice(0, 3).map(e => `${e.symbol}:${e.close}`)
    });
    
    // Check if updateEquityData method exists
    if (typeof exchangeState.updateEquityData === 'function') {
      this.logger.info('🌐 GLOBAL_STATE: Calling exchangeState.updateEquityData...');
      exchangeState.updateEquityData(data);
      this.logger.info('✅ GLOBAL_STATE: exchangeState.updateEquityData COMPLETE');
    } else {
      this.logger.error('❌ GLOBAL_STATE: exchangeState.updateEquityData method not available!');
    }

    // Also convert to legacy format for backward compatibility
    this.logger.info('🌐 GLOBAL_STATE: Converting to legacy symbols format...');
    const legacySymbols: any = {};
    data.forEach(equity => {
      legacySymbols[equity.symbol] = {
        price: equity.close,
        open: equity.open,
        high: equity.high,
        low: equity.low,
        close: equity.close,
        volume: equity.volume
      };
    });
    
    this.logger.info('🌐 GLOBAL_STATE: Updating legacy symbols', {
      legacySymbolCount: Object.keys(legacySymbols).length,
      sampleLegacy: Object.keys(legacySymbols).slice(0, 3)
    });
    
    exchangeState.updateSymbols(legacySymbols);
    this.logger.info('✅ GLOBAL_STATE: Legacy symbols update complete');
    
    // Log final state
    const finalState = exchangeState.getState();
    this.logger.info('🌐 GLOBAL_STATE: EQUITY UPDATE COMPLETE', {
      newEquityDataCount: Object.keys(finalState.equityData).length,
      newSymbolsCount: Object.keys(finalState.symbols).length,
      dataSource: finalState.dataSource,
      lastUpdated: finalState.lastUpdated
    });
  }

  updateOrderData(data: any[]): void {
    this.logger.info('🌐 GLOBAL_STATE: ORDER UPDATE START', { 
      dataCount: data.length,
      sampleOrderIds: data.slice(0, 3).map(o => o.orderId)
    });
    
    if (typeof portfolioState.updateOrderData === 'function') {
      this.logger.info('🌐 GLOBAL_STATE: Calling portfolioState.updateOrderData...');
      portfolioState.updateOrderData(data);
      this.logger.info('✅ GLOBAL_STATE: portfolioState.updateOrderData COMPLETE');
    } else {
      this.logger.error('❌ GLOBAL_STATE: portfolioState.updateOrderData method not available!');
    }
    
    // Log final state
    const finalState = portfolioState.getState();
    this.logger.info('🌐 GLOBAL_STATE: ORDER UPDATE COMPLETE', {
      newOrderCount: Object.keys(finalState.orders).length,
      dataSource: finalState.dataSource,
      lastUpdated: finalState.lastUpdated
    });
  }

  updatePortfolioData(data: any): void {
    this.logger.info('🌐 GLOBAL_STATE: PORTFOLIO UPDATE START', { 
      cashBalance: data.cash_balance,
      totalValue: data.total_value,
      positionCount: data.positions?.length || 0
    });
    
    if (typeof portfolioState.updatePortfolioData === 'function') {
      this.logger.info('🌐 GLOBAL_STATE: Calling portfolioState.updatePortfolioData...');
      portfolioState.updatePortfolioData(data);
      this.logger.info('✅ GLOBAL_STATE: portfolioState.updatePortfolioData COMPLETE');
    } else {
      this.logger.error('❌ GLOBAL_STATE: portfolioState.updatePortfolioData method not available!');
      // Fallback to generic update
      this.logger.info('🌐 GLOBAL_STATE: Using fallback generic update...');
      portfolioState.updateState(data);
    }
    
    // Log final state
    const finalState = portfolioState.getState();
    this.logger.info('🌐 GLOBAL_STATE: PORTFOLIO UPDATE COMPLETE', {
      finalCashBalance: finalState.cashBalance,
      finalTotalValue: finalState.totalValue,
      finalPositionCount: Object.keys(finalState.positions).length,
      dataSource: finalState.dataSource
    });
  }

  getConnectionState(): any {
    const state = connectionState.getState();
    this.logger.debug('🌐 GLOBAL_STATE: Connection state requested', { state });
    return state;
  }

  getAuthState(): any {
    const state = authState.getState();
    this.logger.debug('🌐 GLOBAL_STATE: Auth state requested', { state });
    return state;
  }
}

/**
 * Complete refactored ToastService implementation
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
 * Complete refactored ConfigService implementation - FIXED config access
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
      hasConfig: !!config,
      hasWebsocket: !!(config as any)?.websocket,
      websocketUrl: (config as any)?.websocket?.url,
      configKeys: config ? Object.keys(config) : 'config is null/undefined'
    });
    
    let wsUrl: string;
    
    // PRIORITY 1: Environment variable (YOUR BACKEND)
    if (process.env.REACT_APP_WS_URL) {
      wsUrl = process.env.REACT_APP_WS_URL;
      logger.info('🔍 CONFIG DEBUG: Using REACT_APP_WS_URL (YOUR BACKEND)', { wsUrl });
    }
    // PRIORITY 2: Global config websocket.url
    else if (config?.websocket?.url) {
      wsUrl = config.websocket.url;
      logger.info('🔍 CONFIG DEBUG: Using config.websocket.url', { wsUrl });
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
    // FIXED: Access reconnection config at root level, not under websocket
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
 * FIXED Factory function - USE EXISTING TOKEN MANAGER!
 */
export function createConnectionManagerWithGlobalDeps(tokenManager: TokenManager) {
  logger.info('🔧 FACTORY: Creating ConnectionManager with existing TokenManager...');
  
  const stateManager = new GlobalStateManager();
  const toastService = new GlobalToastService();
  const configService = new GlobalConfigService();
  
  logger.info('🔧 FACTORY: Dependencies created', {
    hasStateManager: !!stateManager,
    hasToastService: !!toastService,
    hasConfigService: !!configService,
    hasTokenManager: !!tokenManager
  });
  
  // Import ConnectionManager
  const { ConnectionManager } = require('../client/connection-manager');
  
  logger.info('🔧 FACTORY: Creating ConnectionManager with all parameters...');
  
  // FIXED: Use the EXISTING tokenManager instead of creating a new one
  const connectionManager = new ConnectionManager(
    tokenManager,     // Use the EXISTING working TokenManager
    stateManager,
    toastService,
    configService
  );
  
  logger.info('✅ FACTORY: ConnectionManager created successfully');
  
  return connectionManager;
}