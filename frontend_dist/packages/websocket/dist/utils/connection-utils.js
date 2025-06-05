// src/utils/connection-utils.ts
import { getLogger } from '@trading-app/logging';
import { connectionState, authState, simulatorState, exchangeState, portfolioState } from '@trading-app/state';
import { toastService } from '@trading-app/toast';
import { config } from '@trading-app/config';
/**
 * Implementation of StateManager that wraps the global state services
 */
export class GlobalStateManager {
    constructor() {
        this.logger = getLogger('GlobalStateManager');
    }
    updateConnectionState(changes) {
        this.logger.debug('Updating connection state', { changes });
        connectionState.updateState(changes);
    }
    updateSimulatorState(changes) {
        this.logger.debug('Updating simulator state', { changes });
        simulatorState.updateState(changes);
    }
    updateExchangeState(changes) {
        this.logger.debug('Updating exchange state', { changes });
        if (changes.symbols) {
            exchangeState.updateSymbols(changes.symbols);
        }
    }
    updatePortfolioState(changes) {
        this.logger.debug('Updating portfolio state', { changes });
        portfolioState.updateState(changes);
    }
    getConnectionState() {
        return connectionState.getState();
    }
    getAuthState() {
        return authState.getState();
    }
}
/**
 * Implementation of ToastService that wraps the global toast service
 */
export class GlobalToastService {
    info(message, duration, id) {
        toastService.info(message, duration, id);
    }
    warning(message, duration, id) {
        toastService.warning(message, duration, id);
    }
    error(message, duration, id) {
        toastService.error(message, duration, id);
    }
    success(message, duration, id) {
        toastService.success(message, duration, id);
    }
}
/**
 * Implementation of ConfigService that wraps the global config
 */
export class GlobalConfigService {
    getWebSocketUrl() {
        return config.wsBaseUrl;
    }
    getReconnectionConfig() {
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
