import { EnhancedLogger } from '../utils/enhanced-logger';
export declare function initializeLogging(): void;
/**
 * Utility function to easily get a child logger instance from the root logger.
 * Ensures the root logger is initialized before creating children.
 * @param name - The name for the child logger (e.g., 'AuthService', 'MyComponent').
 * @returns An EnhancedLogger instance.
 */
export declare function getLogger(name: string): EnhancedLogger;
