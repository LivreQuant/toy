import { SocketClient } from '../client/socket-client';
import { HeartbeatOptions, StateManager } from '../types/connection-types';
export declare class HeartbeatHandler {
    private client;
    private stateManager;
    private options;
    private logger;
    private intervalId;
    private timeoutId;
    private lastTimestamp;
    private events;
    constructor(client: SocketClient, stateManager: StateManager, options: HeartbeatOptions);
    start(): void;
    stop(): void;
    on<T extends keyof typeof this.events.events>(event: T, callback: (data: typeof this.events.events[T]) => void): {
        unsubscribe: () => void;
    };
    private sendHeartbeat;
    private handleHeartbeatResponse;
    private calculateConnectionQuality;
    private handleTimeout;
    dispose(): void;
}
