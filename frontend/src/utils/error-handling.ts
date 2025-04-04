// src/utils/error-handler.ts
import { toastService } from '../services/notification/toast-service';
import { Logger } from './logger';

export enum ErrorSeverity {
  LOW = 'low',       // Minor issues, non-disruptive
  MEDIUM = 'medium', // Affects some functionality
  HIGH = 'high',     // Critical, major functionality broken
  FATAL = 'fatal'    // Application cannot continue
}

export class ErrorHandler {
  private static logger = new Logger('ErrorHandler');

  /**
   * Handle connection errors
   */
  public static handleConnectionError(
    error: Error | string,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    context: string = 'connection'
  ): void {
    const errorMessage = typeof error === 'string' ? error : error.message;
    
    this.logger.error(`${context} error:`, { error, severity });
    
    switch (severity) {
      case ErrorSeverity.LOW:
        toastService.info(`Connection issue: ${errorMessage}`, 5000);
        break;
      case ErrorSeverity.MEDIUM:
        toastService.warning(`Connection problem: ${errorMessage}`, 7000);
        break;
      case ErrorSeverity.HIGH:
        toastService.error(`Connection error: ${errorMessage}`, 10000);
        break;
      case ErrorSeverity.FATAL:
        toastService.error(`Critical connection failure: ${errorMessage}`, 0); // No auto-dismiss
        break;
    }
  }

  /**
   * Handle authentication errors
   */
  public static handleAuthError(
    error: Error | string,
    severity: ErrorSeverity = ErrorSeverity.HIGH,
    context: string = 'authentication'
  ): void {
    const errorMessage = typeof error === 'string' ? error : error.message;
    
    this.logger.error(`${context} error:`, { error, severity });
    
    switch (severity) {
      case ErrorSeverity.MEDIUM:
        toastService.warning(`Authentication issue: ${errorMessage}`, 7000);
        break;
      case ErrorSeverity.HIGH:
      case ErrorSeverity.FATAL:
        toastService.error(`Authentication failed: ${errorMessage}`, 10000);
        break;
      default:
        toastService.warning(`Authentication issue: ${errorMessage}`, 5000);
    }
  }

  /**
   * Handle data errors
   */
  public static handleDataError(
    error: Error | string,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    context: string = 'data'
  ): void {
    const errorMessage = typeof error === 'string' ? error : error.message;
    
    this.logger.error(`${context} error:`, { error, severity });
    
    switch (severity) {
      case ErrorSeverity.LOW:
        toastService.info(`Data issue: ${errorMessage}`, 5000);
        break;
      case ErrorSeverity.MEDIUM:
        toastService.warning(`Data problem: ${errorMessage}`, 7000);
        break;
      case ErrorSeverity.HIGH:
      case ErrorSeverity.FATAL:
        toastService.error(`Data error: ${errorMessage}`, 10000);
        break;
    }
  }
}