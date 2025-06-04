export declare class EventEmitter<T extends Record<string, any>> {
    readonly events: T;
    private handlers;
    private logger;
    constructor();
    /**
     * Register an event handler
     */
    on<K extends keyof T>(event: K, handler: (data: T[K]) => void): {
        unsubscribe: () => void;
    };
    /**
     * Register a one-time event handler
     */
    once<K extends keyof T>(event: K, handler: (data: T[K]) => void): {
        unsubscribe: () => void;
    };
    /**
     * Emit an event with data
     */
    emit<K extends keyof T>(event: K, data: T[K]): void;
    /**
     * Remove all event handlers
     */
    clear(): void;
    /**
     * Get the number of handlers for an event
     */
    handlerCount(event: keyof T): number;
}
