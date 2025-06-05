// src/utils/connection-utils.ts
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
    return config.wsBaseUrl;
  }

  getReconnectionConfig(): {
    initialDelayMs: number;
    maxDelayMs: number;
    jitterFactor: number;
    maxAttempts: number;
  } {
    return config.reconnection;
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