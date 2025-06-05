export interface RetryOptions {
    maxAttempts?: number;
    initialDelay?: number;
    maxDelay?: number;
    backoffFactor?: number;
    retryCondition?: (error: any) => boolean;
    onRetry?: (attempt: number, error: any) => void;
}
export declare class RetryError extends Error {
    readonly attempts: number;
    readonly lastError: Error;
    constructor(message: string, attempts: number, lastError: Error);
}
/**
 * Retry a function with exponential backoff
 * @param fn - Function to retry
 * @param options - Retry configuration options
 * @returns Promise that resolves with the function result or rejects with RetryError
 */
export declare function retryWithBackoff<T>(fn: () => Promise<T>, options?: RetryOptions): Promise<T>;
/**
 * Sleep for a specified number of milliseconds
 * @param ms - Milliseconds to sleep
 * @returns Promise that resolves after the delay
 */
export declare function sleep(ms: number): Promise<void>;
/**
 * Retry specifically for network operations
 * @param fn - Network function to retry
 * @param options - Additional retry options
 * @returns Promise with network-specific retry logic
 */
export declare function retryNetworkOperation<T>(fn: () => Promise<T>, options?: Omit<RetryOptions, 'retryCondition'> & {
    retryOnStatus?: number[];
}): Promise<T>;
