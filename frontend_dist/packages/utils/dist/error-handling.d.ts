export type ErrorSeverity = 'low' | 'medium' | 'high' | 'fatal';
/**
 * Interface for toast service - allows dependency injection
 */
export interface ToastService {
    info(message: string, duration?: number): void;
    warning(message: string, duration?: number): void;
    error(message: string, duration?: number): void;
}
/**
 * Set the toast service for error handling
 */
export declare function setToastService(service: ToastService): void;
/**
 * Handles an error and returns a standardized error result
 */
export declare function handleError(error: string | Error, context: string, severity?: ErrorSeverity, details?: Record<string, any>): {
    success: false;
    error: string;
};
/**
 * Wraps an async function with error handling
 */
export declare function withErrorHandling<T>(fn: () => Promise<T>, context: string, severity?: ErrorSeverity): Promise<T>;
/**
 * Helper to create domain-specific error handler
 */
export declare function createErrorHandler(domainContext: string): {
    handleError: (error: string | Error, context: string, severity?: ErrorSeverity, details?: Record<string, any>) => {
        success: false;
        error: string;
    };
    withErrorHandling: <T>(fn: () => Promise<T>, context: string, severity?: ErrorSeverity) => Promise<T>;
};
