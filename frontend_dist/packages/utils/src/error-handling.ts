// src/error-handling.ts
import { getLogger } from '@trading-app/logging';

export type ErrorSeverity = 'low' | 'medium' | 'high' | 'fatal';

const logger = getLogger('ErrorHandling');

/**
 * Interface for toast service - allows dependency injection
 */
export interface ToastService {
  info(message: string, duration?: number): void;
  warning(message: string, duration?: number): void;
  error(message: string, duration?: number): void;
}

// Toast service singleton - set by main app
let toastService: ToastService | null = null;

/**
 * Set the toast service for error handling
 */
export function setToastService(service: ToastService): void {
  toastService = service;
}

/**
 * Handles an error and returns a standardized error result
 */
export function handleError(
  error: string | Error,
  context: string,
  severity: ErrorSeverity = 'medium',
  details?: Record<string, any>
): { success: false; error: string } {
  const errorMessage = error instanceof Error ? error.message : error;
  
  // Log the error with appropriate level
  logError(errorMessage, context, severity, details);
  
  // Display user notification if toast service is available
  if (toastService) {
    notifyUser(errorMessage, severity);
  }
  
  return {
    success: false,
    error: errorMessage
  };
}

/**
 * Logs an error with appropriate severity level
 */
function logError(
  error: string,
  context: string,
  severity: ErrorSeverity,
  details?: Record<string, any>
): void {
  const logData = {
    context,
    severity,
    ...details
  };
  
  switch (severity) {
    case 'low':
      logger.debug(`[${context}] ${error}`, logData);
      break;
    case 'medium':
      logger.warn(`[${context}] ${error}`, logData);
      break;
    case 'high':
    case 'fatal':
      logger.error(`[${context}] ${error}`, logData);
      break;
  }
}

/**
 * Shows a user-facing notification based on severity
 */
function notifyUser(message: string, severity: ErrorSeverity): void {
  if (!toastService) return;
  
  let duration: number;
  
  switch (severity) {
    case 'low':
      duration = 4000;
      toastService.info(message, duration);
      break;
    case 'medium':
      duration = 6000;
      toastService.warning(message, duration);
      break;
    case 'high':
      duration = 8000;
      toastService.error(message, duration);
      break;
    case 'fatal':
      // Manual dismiss for fatal errors
      toastService.error(message, 0);
      break;
  }
}

/**
 * Wraps an async function with error handling
 */
export function withErrorHandling<T>(
  fn: () => Promise<T>,
  context: string,
  severity: ErrorSeverity = 'medium'
): Promise<T> {
  return fn().catch(error => {
    handleError(error, context, severity);
    throw error; // Re-throw to allow caller to handle
  });
}

/**
 * Helper to create domain-specific error handler
 */
export function createErrorHandler(domainContext: string) {
  return {
    handleError: (error: string | Error, context: string, severity: ErrorSeverity = 'medium', details?: Record<string, any>) =>
      handleError(error, `${domainContext}.${context}`, severity, details),
      
    withErrorHandling: <T>(fn: () => Promise<T>, context: string, severity: ErrorSeverity = 'medium') =>
      withErrorHandling(fn, `${domainContext}.${context}`, severity)
  };
}