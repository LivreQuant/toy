// src/disposable.ts

/**
 * Interface for objects that need explicit cleanup of resources.
 * Promotes resource management, especially for subscriptions, timers,
 * or other asynchronous operations.
 */
export interface Disposable {
    /**
     * Performs cleanup operations like unsubscribing from observables,
     * clearing timers, or closing connections.
     */
    dispose(): void;
}

/**
 * Type guard to check if an object implements the Disposable interface.
 * @param obj - The object to check.
 * @returns True if the object has a `dispose` method, false otherwise.
 */
export function isDisposable(obj: any): obj is Disposable {
    return obj !== null && typeof obj === 'object' && typeof obj.dispose === 'function';
}