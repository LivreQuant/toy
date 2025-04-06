// src/utils/app-error-handler.ts
import { ErrorHandler, ErrorSeverity } from './error-handler';
import { Logger } from './logger';
import { ToastService } from '../services/notification/toast-service';

/**
 * Singleton implementation of ErrorHandler to ensure consistent error handling
 */
export class AppErrorHandler {
  private static instance: ErrorHandler;
  
  private constructor() {
    // Private constructor to enforce singleton pattern
  }
  
  public static initialize(logger: Logger, toastService: ToastService): void {
    if (!AppErrorHandler.instance) {
      AppErrorHandler.instance = new ErrorHandler(logger, toastService);
    }
  }
  
  public static getInstance(): ErrorHandler {
    if (!AppErrorHandler.instance) {
      throw new Error('AppErrorHandler not initialized. Call initialize() first.');
    }
    return AppErrorHandler.instance;
  }
  
  // Convenience methods that delegate to the singleton instance
  public static handleConnectionError(error: Error | string, severity?: ErrorSeverity, context?: string): void {
    AppErrorHandler.getInstance().handleConnectionError(error, severity, context);
  }
  
  public static handleAuthError(error: Error | string, severity?: ErrorSeverity, context?: string): void {
    AppErrorHandler.getInstance().handleAuthError(error, severity, context);
  }
  
  public static handleDataError(error: Error | string, severity?: ErrorSeverity, context?: string): void {
    AppErrorHandler.getInstance().handleDataError(error, severity, context);
  }
  
  public static handleGenericError(error: Error | string, severity?: ErrorSeverity, context?: string): void {
    AppErrorHandler.getInstance().handleGenericError(error, severity, context);
  }
}