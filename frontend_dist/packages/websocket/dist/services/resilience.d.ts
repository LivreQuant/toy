import { TokenManager } from '@trading-app/auth';
import { Disposable } from '@trading-app/utils';
import { ToastService, ResilienceOptions } from '../types/connection-types';
export declare enum ResilienceState {
    STABLE = "stable",
    DEGRADED = "degraded",
    RECOVERING = "recovering",
    SUSPENDED = "suspended",
    FAILED = "failed"
}
export declare class Resilience implements Disposable {
    private tokenManager;
    private toastService;
    private logger;
    private state;
    private reconnectAttempt;
    private failureCount;
    private lastFailureTime;
    private reconnectTimer;
    private suspensionTimer;
    private isDisposed;
    readonly options: Required<ResilienceOptions>;
    private events;
    private static DEFAULT_OPTIONS;
    constructor(tokenManager: TokenManager, toastService: ToastService, options?: ResilienceOptions);
    getState(): {
        state: ResilienceState;
        attempt: number;
        failureCount: number;
    };
    on<T extends keyof typeof this.events.events>(event: T, callback: (data: typeof this.events.events[T]) => void): {
        unsubscribe: () => void;
    };
    recordFailure(errorInfo?: any): void;
    attemptReconnection(connectCallback: () => Promise<boolean>): Promise<boolean>;
    reset(): void;
    updateAuthState(isAuthenticated: boolean): void;
    private executeReconnectAttempt;
    private calculateBackoffDelay;
    private transitionToState;
    private enterSuspendedStateLogic;
    private exitSuspendedState;
    private enterFailedStateLogic;
    private stopTimers;
    dispose(): void;
}
