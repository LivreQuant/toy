// src/disposable.ts
/**
 * Type guard to check if an object implements the Disposable interface.
 * @param obj - The object to check.
 * @returns True if the object has a `dispose` method, false otherwise.
 */
export function isDisposable(obj) {
    return obj !== null && typeof obj === 'object' && typeof obj.dispose === 'function';
}
