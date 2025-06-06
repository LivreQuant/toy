import { TokenManager } from '@trading-app/auth';
import { Disposable } from '@trading-app/utils';
import { ConnectionDesiredState, ConnectionManagerOptions, ToastService, StateManager, ConfigService } from '../types/connection-types';
export declare class ConnectionManager implements Disposable {
    private tokenManager;
    private stateManager;
    private toastService;
    private configService;
    private logger;
    private socketClient;
    private heartbeat;
    private resilience;
    private sessionHandler;
    private simulatorClient;
    private isDisposed;
    private hasAuthInitialized;
    desiredState: ConnectionDesiredState;
    private events;
    constructor(tokenManager: TokenManager, stateManager: StateManager, toastService: ToastService, configService: ConfigService, options?: ConnectionManagerOptions);
    private waitForAuthInitialization;
    private setupListeners;
    resetState(): void;
    setDesiredState(state: Partial<ConnectionDesiredState>): void;
    private syncConnectionState;
    private syncSimulatorState;
    connect(): Promise<boolean>;
    disconnect(reason?: string): Promise<boolean>;
    attemptRecovery(reason?: string): Promise<boolean>;
    manualReconnect(): Promise<boolean>;
    private handleDeviceIdInvalidation;
    startSimulator(): Promise<{
        success: boolean;
        status?: string;
        error?: string;
    }>;
    stopSimulator(): Promise<{
        success: boolean;
        status?: string;
        error?: string;
    }>;
    on<T extends keyof typeof this.events.events>(event: T, callback: (data: typeof this.events.events[T]) => void): {
        unsubscribe: () => void;
    };
    dispose(): void;
}
