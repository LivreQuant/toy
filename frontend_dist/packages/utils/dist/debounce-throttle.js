// src/debounce-throttle.ts
/**
 * Debounce function calls
 * @param func - Function to debounce
 * @param wait - Wait time in milliseconds
 * @param immediate - Execute immediately on first call
 * @returns Debounced function
 */
export function debounce(func, wait, immediate = false) {
    let timeout = null;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate)
                func(...args);
        };
        const callNow = immediate && !timeout;
        if (timeout)
            clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow)
            func(...args);
    };
}
/**
 * Throttle function calls
 * @param func - Function to throttle
 * @param limit - Time limit in milliseconds
 * @returns Throttled function
 */
export function throttle(func, limit) {
    let inThrottle = false;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}
/**
 * Create a cancellable timeout
 * @param callback - Function to call after timeout
 * @param delay - Delay in milliseconds
 * @returns Object with cancel function
 */
export function createCancellableTimeout(callback, delay) {
    const timeoutId = setTimeout(callback, delay);
    return {
        cancel: () => clearTimeout(timeoutId)
    };
}
/**
 * Create a cancellable interval
 * @param callback - Function to call on each interval
 * @param interval - Interval in milliseconds
 * @returns Object with cancel function
 */
export function createCancellableInterval(callback, interval) {
    const intervalId = setInterval(callback, interval);
    return {
        cancel: () => clearInterval(intervalId)
    };
}
