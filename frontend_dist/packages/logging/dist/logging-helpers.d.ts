import { EnhancedLogger } from './enhanced-logger';
/**
 * Logs the execution time of an async function
 */
export declare function logExecutionTime<T>(logger: EnhancedLogger, operationName: string, fn: () => Promise<T>): Promise<T>;
/**
 * Creates log context with standard metadata
 */
export declare function createLogContext(baseContext?: Record<string, any>, extraContext?: Record<string, any>): Record<string, any>;
/**
 * Decorates a class method to log execution time
 */
export declare function LogExecutionTime(logger: EnhancedLogger, operationNamePrefix?: string): (target: any, propertyKey: string, descriptor: PropertyDescriptor) => PropertyDescriptor;
/**
 * Formats an error for logging
 */
export declare function formatError(error: any): Record<string, any>;
/**
 * Creates a scoped logger with additional context
 */
export declare function createScopedLogger(baseLogger: EnhancedLogger, scope: string, baseContext?: Record<string, any>): {
    debug: (message: string, context?: Record<string, any>) => void;
    info: (message: string, context?: Record<string, any>) => void;
    warn: (message: string, context?: Record<string, any>) => void;
    error: (message: string, context?: Record<string, any>) => void;
};
