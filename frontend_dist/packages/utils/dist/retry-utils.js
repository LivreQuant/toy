var __rest = (this && this.__rest) || function (s, e) {
    var t = {};
    for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p) && e.indexOf(p) < 0)
        t[p] = s[p];
    if (s != null && typeof Object.getOwnPropertySymbols === "function")
        for (var i = 0, p = Object.getOwnPropertySymbols(s); i < p.length; i++) {
            if (e.indexOf(p[i]) < 0 && Object.prototype.propertyIsEnumerable.call(s, p[i]))
                t[p[i]] = s[p[i]];
        }
    return t;
};
// src/retry-utils.ts
import { getLogger } from '@trading-app/logging';
export class RetryError extends Error {
    constructor(message, attempts, lastError) {
        super(message);
        this.name = 'RetryError';
        this.attempts = attempts;
        this.lastError = lastError;
    }
}
/**
 * Retry a function with exponential backoff
 * @param fn - Function to retry
 * @param options - Retry configuration options
 * @returns Promise that resolves with the function result or rejects with RetryError
 */
export async function retryWithBackoff(fn, options = {}) {
    const logger = getLogger('RetryUtils');
    const { maxAttempts = 3, initialDelay = 1000, maxDelay = 30000, backoffFactor = 2, retryCondition = () => true, onRetry } = options;
    let attempt = 1;
    let delay = initialDelay;
    while (attempt <= maxAttempts) {
        try {
            const result = await fn();
            if (attempt > 1) {
                logger.info(`Operation succeeded on attempt ${attempt}`);
            }
            return result;
        }
        catch (error) {
            if (attempt === maxAttempts || !retryCondition(error)) {
                throw new RetryError(`Operation failed after ${attempt} attempts`, attempt, error);
            }
            logger.warn(`Attempt ${attempt} failed, retrying in ${delay}ms`, {
                error: error.message,
                attempt,
                maxAttempts
            });
            if (onRetry) {
                try {
                    onRetry(attempt, error);
                }
                catch (retryError) {
                    logger.error('Error in retry callback', { error: retryError.message });
                }
            }
            await sleep(delay);
            attempt++;
            delay = Math.min(delay * backoffFactor, maxDelay);
        }
    }
    throw new Error('Retry logic error - should not reach here');
}
/**
 * Sleep for a specified number of milliseconds
 * @param ms - Milliseconds to sleep
 * @returns Promise that resolves after the delay
 */
export function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
/**
 * Retry specifically for network operations
 * @param fn - Network function to retry
 * @param options - Additional retry options
 * @returns Promise with network-specific retry logic
 */
export async function retryNetworkOperation(fn, options = {}) {
    const { retryOnStatus = [408, 429, 500, 502, 503, 504] } = options, retryOptions = __rest(options, ["retryOnStatus"]);
    return retryWithBackoff(fn, Object.assign(Object.assign({}, retryOptions), { retryCondition: (error) => {
            var _a;
            // Retry on network errors
            if (error.name === 'NetworkError' || ((_a = error.message) === null || _a === void 0 ? void 0 : _a.includes('network'))) {
                return true;
            }
            // Retry on specific HTTP status codes
            if (error.status && retryOnStatus.includes(error.status)) {
                return true;
            }
            // Don't retry on authentication errors
            if (error.status === 401 || error.status === 403) {
                return false;
            }
            return true;
        } }));
}
