import { Disposable } from '@trading-app/utils';
import { SocketClient } from '../client/socket-client';
import { HeartbeatOptions, StateManager } from '../types/connection-types';
export declare class Heartbeat implements Disposable {
    private client;
    private stateManager;
    private logger;
    private heartbeatIntervalId;
    private heartbeatTimeoutId;
    private isStarted;
    private isDisposed;
    private lastHeartbeatTimestamp;
    private events;
    private options;
    constructor(client: SocketClient, stateManager: StateManager, options?: Partial<HeartbeatOptions>);
    isActive(): boolean;
    start(): void;
    stop(): void;
    on<T extends keyof typeof this.events.events>(event: T, callback: (data: typeof this.events.events[T]) => void): {
        unsubscribe: () => void;
    };
    private scheduleNextHeartbeat;
    private sendHeartbeat;
    private handleHeartbeatResponse;
    private calculateConnectionQuality;
    private handleHeartbeatTimeout;
    private clearHeartbeatInterval;
    private clearHeartbeatTimeout;
    dispose(): void;
}
