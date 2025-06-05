import { BehaviorSubject, Observable } from 'rxjs';
/**
 * Base class for state management services
 * Provides common functionality for state management with RxJS
 */
export declare abstract class BaseStateService<T> {
    protected logger: import("@trading-app/logging").EnhancedLogger;
    protected state$: BehaviorSubject<T>;
    constructor(initialState: T);
    /**
     * Select a slice of the state
     * @param selector - Function to select part of the state
     * @returns Observable of the selected state slice
     */
    select<K>(selector: (state: T) => K): Observable<K>;
    /**
     * Get the entire state as an observable
     */
    getState$(): Observable<T>;
    /**
     * Get the current state snapshot
     */
    getState(): T;
    /**
     * Update the state with partial changes
     * @param changes - Partial state changes to apply
     */
    updateState(changes: Partial<T>): void;
    /**
     * Replace the entire state
     * @param newState - The new state to set
     */
    setState(newState: T): void;
    /**
     * Reset state to initial state
     */
    abstract reset(): void;
    /**
     * Clean up resources
     */
    dispose(): void;
}
