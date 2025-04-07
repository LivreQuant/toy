// src/utils/app-error-handler.ts
import { ErrorHandler, ErrorSeverity } from './error-handler';
import { EnhancedLogger } from './enhanced-logger'; // Use your chosen logger type
import { ToastService } from '../services/notification/toast-service';

/**
 * Singleton wrapper for the ErrorHandler class.
 * Provides static methods for easy access to error handling logic
 * throughout the application after initialization.
 */
export class AppErrorHandler {
  private static instance: ErrorHandler | null = null; // Allow null initially

  // Private constructor prevents external instantiation
  private constructor() {}

  /**
   * Initializes the singleton ErrorHandler instance.
   * MUST be called once during application startup (e.g., in index.tsx or bootstrapper).
   * @param logger - The Logger instance to be used by the ErrorHandler.
   * @param toastService - The ToastService instance for displaying notifications.
   */
  public static initialize(logger: EnhancedLogger, toastService: ToastService): void {
    if (!AppErrorHandler.instance) {
      AppErrorHandler.instance = new ErrorHandler(logger, toastService);
      // Use the passed logger instance for initialization message
      logger.info('AppErrorHandler initialized successfully.');
    } else {
       // Use the passed logger instance for warning message
       logger.warn('AppErrorHandler already initialized.');
    }
  }

  /**
   * Gets the singleton ErrorHandler instance.
   * Throws an error if initialize() has not been called first.
   * @returns The configured ErrorHandler instance.
   */
  public static getInstance(): ErrorHandler {
    if (!AppErrorHandler.instance) {
      // Provide a more helpful error message
      const initError = new Error('AppErrorHandler not initialized. Call AppErrorHandler.initialize() during application startup.');
      console.error(initError.message); // Log error before throwing
      throw initError;
    }
    return AppErrorHandler.instance;
  }

  // --- Convenience static methods ---
  // These delegate directly to the singleton instance's methods.

  /**
   * Handles connection-related errors via the singleton instance.
   * @param error - The error object or message string.
   * @param severity - Optional severity level.
   * @param context - Optional context string.
   * @param details - Optional additional details for logging.
   */
  public static handleConnectionError(
      error: Error | string,
      severity?: ErrorSeverity,
      context?: string,
      details?: any // Optional additional details
    ): void {
    try {
        AppErrorHandler.getInstance().handleConnectionError(error, severity, context, details);
    } catch (initError) {
        // Fallback logging if getInstance fails (shouldn't happen if initialized correctly)
        console.error("CRITICAL: AppErrorHandler not initialized when handling ConnectionError", { error, context, details });
    }
  }

  /**
   * Handles authentication-related errors via the singleton instance.
   * @param error - The error object or message string.
   * @param severity - Optional severity level.
   * @param context - Optional context string.
   * @param details - Optional additional details for logging.
   */
  public static handleAuthError(
      error: Error | string,
      severity?: ErrorSeverity,
      context?: string,
      details?: any
    ): void {
     try {
        AppErrorHandler.getInstance().handleAuthError(error, severity, context, details);
     } catch (initError) {
        console.error("CRITICAL: AppErrorHandler not initialized when handling AuthError", { error, context, details });
     }
  }

  /**
   * Handles data processing or API data errors via the singleton instance.
   * @param error - The error object or message string.
   * @param severity - Optional severity level.
   * @param context - Optional context string.
   * @param details - Optional additional details for logging.
   */
  public static handleDataError(
      error: Error | string,
      severity?: ErrorSeverity,
      context?: string,
      details?: any
    ): void {
     try {
        AppErrorHandler.getInstance().handleDataError(error, severity, context, details);
     } catch (initError) {
         console.error("CRITICAL: AppErrorHandler not initialized when handling DataError", { error, context, details });
     }
  }

  /**
   * Handles generic or unexpected application errors via the singleton instance.
   * @param error - The error object or message string.
   * @param severity - Optional severity level.
   * @param context - Optional context string.
   * @param details - Optional additional details for logging.
   */
  public static handleGenericError(
      error: Error | string,
      severity?: ErrorSeverity,
      context?: string,
      details?: any
    ): void {
      try {
        AppErrorHandler.getInstance().handleGenericError(error, severity, context, details);
      } catch (initError) {
          console.error("CRITICAL: AppErrorHandler not initialized when handling GenericError", { error, context, details });
      }
  }
}