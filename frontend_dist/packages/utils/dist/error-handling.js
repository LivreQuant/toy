// src/error-handling.ts
import { getLogger } from '@trading-app/logging';
const logger = getLogger('ErrorHandling');
// Toast service singleton - set by main app
let toastService = null;
/**
 * Set the toast service for error handling
 */
export function setToastService(service) {
    toastService = service;
}
/**
 * Handles an error and returns a standardized error result
 */
export function handleError(error, context, severity = 'medium', details) {
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
function logError(error, context, severity, details) {
    const logData = Object.assign({ context,
        severity }, details);
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
function notifyUser(message, severity) {
    if (!toastService)
        return;
    let duration;
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
export function withErrorHandling(fn, context, severity = 'medium') {
    return fn().catch(error => {
        handleError(error, context, severity);
        throw error; // Re-throw to allow caller to handle
    });
}
/**
 * Helper to create domain-specific error handler
 */
export function createErrorHandler(domainContext) {
    return {
        handleError: (error, context, severity = 'medium', details) => handleError(error, `${domainContext}.${context}`, severity, details),
        withErrorHandling: (fn, context, severity = 'medium') => withErrorHandling(fn, `${domainContext}.${context}`, severity)
    };
}
