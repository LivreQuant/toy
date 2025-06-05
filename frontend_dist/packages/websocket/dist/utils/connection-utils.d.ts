import { StateManager, ToastService, ConfigService } from '../types/connection-types';
/**
 * Implementation of StateManager that wraps the global state services
 */
export declare class GlobalStateManager implements StateManager {
    private logger;
    updateConnectionState(changes: any): void;
    updateSimulatorState(changes: any): void;
    updateExchangeState(changes: any): void;
    updatePortfolioState(changes: any): void;
    getConnectionState(): any;
    getAuthState(): any;
}
/**
 * Implementation of ToastService that wraps the global toast service
 */
export declare class GlobalToastService implements ToastService {
    info(message: string, duration?: number, id?: string): void;
    warning(message: string, duration?: number, id?: string): void;
    error(message: string, duration?: number, id?: string): void;
    success(message: string, duration?: number, id?: string): void;
}
/**
 * Implementation of ConfigService that wraps the global config
 */
export declare class GlobalConfigService implements ConfigService {
    getWebSocketUrl(): string;
    getReconnectionConfig(): {
        initialDelayMs: number;
        maxDelayMs: number;
        jitterFactor: number;
        maxAttempts: number;
    };
}
/**
 * Factory function to create a connection manager with global dependencies
 */
export declare function createConnectionManagerWithGlobalDeps(): {
    stateManager: GlobalStateManager;
    toastService: GlobalToastService;
    configService: GlobalConfigService;
};
