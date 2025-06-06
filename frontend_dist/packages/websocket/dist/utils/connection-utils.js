// frontend_dist/packages/websocket/src/utils/connection-utils.ts
import { getLogger } from '@trading-app/logging';
import { connectionState, authState, simulatorState, exchangeState, portfolioState } from '@trading-app/state';
import { toastService } from '@trading-app/toast';
import { config } from '@trading-app/config';
var logger = getLogger('ConnectionUtils');
/**
 * Implementation of StateManager that wraps the global state services
 */
var GlobalStateManager = /** @class */ (function () {
    function GlobalStateManager() {
        this.logger = getLogger('GlobalStateManager');
    }
    GlobalStateManager.prototype.updateConnectionState = function (changes) {
        this.logger.debug('Updating connection state', { changes: changes });
        connectionState.updateState(changes);
    };
    GlobalStateManager.prototype.updateSimulatorState = function (changes) {
        this.logger.debug('Updating simulator state', { changes: changes });
        simulatorState.updateState(changes);
    };
    GlobalStateManager.prototype.updateExchangeState = function (changes) {
        this.logger.debug('Updating exchange state', { changes: changes });
        if (changes.symbols) {
            exchangeState.updateSymbols(changes.symbols);
        }
    };
    GlobalStateManager.prototype.updatePortfolioState = function (changes) {
        this.logger.debug('Updating portfolio state', { changes: changes });
        portfolioState.updateState(changes);
    };
    GlobalStateManager.prototype.getConnectionState = function () {
        return connectionState.getState();
    };
    GlobalStateManager.prototype.getAuthState = function () {
        return authState.getState();
    };
    return GlobalStateManager;
}());
export { GlobalStateManager };
/**
 * Implementation of ToastService that wraps the global toast service
 */
var GlobalToastService = /** @class */ (function () {
    function GlobalToastService() {
    }
    GlobalToastService.prototype.info = function (message, duration, id) {
        toastService.info(message, duration, id);
    };
    GlobalToastService.prototype.warning = function (message, duration, id) {
        toastService.warning(message, duration, id);
    };
    GlobalToastService.prototype.error = function (message, duration, id) {
        toastService.error(message, duration, id);
    };
    GlobalToastService.prototype.success = function (message, duration, id) {
        toastService.success(message, duration, id);
    };
    return GlobalToastService;
}());
export { GlobalToastService };
/**
 * Implementation of ConfigService that wraps the global config
 */
var GlobalConfigService = /** @class */ (function () {
    function GlobalConfigService() {
    }
    GlobalConfigService.prototype.getWebSocketUrl = function () {
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
            config: config,
            hasWsBaseUrl: !!(config === null || config === void 0 ? void 0 : config.wsBaseUrl),
            wsBaseUrl: config === null || config === void 0 ? void 0 : config.wsBaseUrl,
            configKeys: config ? Object.keys(config) : 'config is null/undefined'
        });
        var wsUrl;
        // PRIORITY 1: Environment variable (YOUR BACKEND)
        if (process.env.REACT_APP_WS_URL) {
            wsUrl = process.env.REACT_APP_WS_URL;
            logger.info('🔍 CONFIG DEBUG: Using REACT_APP_WS_URL (YOUR BACKEND)', { wsUrl: wsUrl });
        }
        // PRIORITY 2: Global config wsBaseUrl
        else if (config === null || config === void 0 ? void 0 : config.wsBaseUrl) {
            wsUrl = config.wsBaseUrl;
            logger.info('🔍 CONFIG DEBUG: Using config.wsBaseUrl', { wsUrl: wsUrl });
        }
        // PRIORITY 3: Development default (YOUR BACKEND)
        else if (process.env.NODE_ENV === 'development') {
            wsUrl = 'ws://trading.local/ws';
            logger.info('🔍 CONFIG DEBUG: Development default - YOUR BACKEND', { wsUrl: wsUrl });
        }
        // PRIORITY 4: Production fallback
        else {
            if (typeof window !== 'undefined') {
                var hostname = window.location.hostname;
                var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                wsUrl = "".concat(protocol, "//").concat(hostname, "/ws");
                logger.info('🔍 CONFIG DEBUG: Production fallback', { wsUrl: wsUrl });
            }
            else {
                // Server-side rendering fallback
                wsUrl = 'ws://trading.local/ws';
                logger.info('🔍 CONFIG DEBUG: SSR fallback - YOUR BACKEND', { wsUrl: wsUrl });
            }
        }
        logger.info('🔍 CONFIG DEBUG: Final WebSocket URL resolved', {
            finalUrl: wsUrl,
            source: 'getWebSocketUrl method'
        });
        logger.info('🚨 CRITICAL: React runs on localhost:3000, WebSocket connects to', { wsUrl: wsUrl });
        return wsUrl;
    };
    GlobalConfigService.prototype.getReconnectionConfig = function () {
        var reconnectionConfig = (config === null || config === void 0 ? void 0 : config.reconnection) || {
            initialDelayMs: 1000,
            maxDelayMs: 30000,
            jitterFactor: 0.3,
            maxAttempts: 10
        };
        logger.info('🔍 CONFIG DEBUG: Reconnection config', { reconnectionConfig: reconnectionConfig });
        return reconnectionConfig;
    };
    return GlobalConfigService;
}());
export { GlobalConfigService };
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
