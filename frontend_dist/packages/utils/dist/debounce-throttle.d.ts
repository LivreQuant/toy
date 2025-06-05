/**
 * Debounce function calls
 * @param func - Function to debounce
 * @param wait - Wait time in milliseconds
 * @param immediate - Execute immediately on first call
 * @returns Debounced function
 */
export declare function debounce<T extends (...args: any[]) => any>(func: T, wait: number, immediate?: boolean): (...args: Parameters<T>) => void;
/**
 * Throttle function calls
 * @param func - Function to throttle
 * @param limit - Time limit in milliseconds
 * @returns Throttled function
 */
export declare function throttle<T extends (...args: any[]) => any>(func: T, limit: number): (...args: Parameters<T>) => void;
/**
 * Create a cancellable timeout
 * @param callback - Function to call after timeout
 * @param delay - Delay in milliseconds
 * @returns Object with cancel function
 */
export declare function createCancellableTimeout(callback: () => void, delay: number): {
    cancel: () => void;
};
/**
 * Create a cancellable interval
 * @param callback - Function to call on each interval
 * @param interval - Interval in milliseconds
 * @returns Object with cancel function
 */
export declare function createCancellableInterval(callback: () => void, interval: number): {
    cancel: () => void;
};
