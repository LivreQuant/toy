// src/utils/error-handler.ts
import { ToastService } from '../services/notification/toast-service'; // Import service instance type
import { EnhancedLogger } from './enhanced-logger'; // Use your chosen logger type

// Define severity levels for errors
export enum ErrorSeverity {
    LOW = 'low',       // Minor issues, potentially recoverable, info/debug level
    MEDIUM = 'medium',   // Recoverable errors, may impact functionality, warn level
    HIGH = 'high',     // Significant errors, likely user-impacting, error level
    FATAL = 'fatal'    // Unrecoverable errors, may require app reload/restart, critical/error level
}

// Structure for additional error details
interface ErrorDetails {
    // Include the original error object if available
    originalError?: Error | unknown;
    // Add any other relevant context
    [key: string]: any;
}


/**
 * Handles application errors by logging them appropriately and displaying
 * user-friendly notifications via the injected ToastService.
 * Designed to be instantiated (e.g., within AppErrorHandler) and used across services.
 */
export class ErrorHandler {
    // Use readonly for injected dependencies that shouldn't change
    private readonly logger: EnhancedLogger;
    private readonly toastService: ToastService;

    /**
     * Creates an instance of ErrorHandler.
     * @param loggerInstance - The Logger instance for recording errors.
     * @param toastServiceInstance - The ToastService instance for displaying notifications.
     */
    constructor(loggerInstance: EnhancedLogger, toastServiceInstance: ToastService) {
        // Create a child logger specific to the ErrorHandler instance
        this.logger = loggerInstance.createChild('ErrorHandler');
        this.toastService = toastServiceInstance;
        this.logger.info('ErrorHandler instance created.');
    }

    /**
     * Central logging method for different error types.
     */
    private logError(
        level: 'error' | 'warn' | 'info' | 'debug',
        prefix: string,
        error: Error | string,
        context?: string,
        severity?: ErrorSeverity,
        details?: ErrorDetails
    ): void {
        const errorMessage = typeof error === 'string' ? error : error.message;
        const logContext = {
            context: context || 'general',
            severity: severity || ErrorSeverity.MEDIUM, // Default severity if not provided
            // Include stack trace for Error objects
            ...(typeof error !== 'string' && error?.stack && { stack: error.stack.split('\n').slice(0, 5).join('\n') }), // Limit stack trace length
            ...details // Spread additional details
        };

        // Use appropriate logger method based on level
        this.logger[level](`${prefix}: ${errorMessage}`, logContext);
    }

    /**
     * Central notification method.
     */
    private notifyUser(
        type: 'error' | 'warning' | 'info',
        message: string,
        severity: ErrorSeverity,
        duration?: number // Allow overriding default duration
    ): void {
        let toastDuration = duration; // Use provided duration if available

        if (!toastDuration) {
             // Default durations based on severity
             switch (severity) {
                 case ErrorSeverity.LOW: toastDuration = 4000; break;
                 case ErrorSeverity.MEDIUM: toastDuration = 6000; break;
                 case ErrorSeverity.HIGH: toastDuration = 8000; break;
                 case ErrorSeverity.FATAL: toastDuration = 0; break; // 0 = manual dismiss
                 default: toastDuration = 5000;
             }
        }

        // Map severity/type to toast function
        switch (type) {
            case 'error':
                this.toastService.error(message, toastDuration);
                break;
            case 'warning':
                this.toastService.warning(message, toastDuration);
                break;
            case 'info':
                this.toastService.info(message, toastDuration);
                break;
        }
    }


    /**
     * Handles connection-related errors (WebSocket, HTTP network issues).
     * @param error - The error object or message string.
     * @param severity - Optional severity (default: MEDIUM).
     * @param context - Optional context string (e.g., 'WebSocket', 'HttpClient').
     * @param details - Optional additional details.
     */
    public handleConnectionError(
        error: Error | string,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: string = 'connection',
        details?: ErrorDetails
    ): void {
        const errorMessage = typeof error === 'string' ? error : error.message;
        this.logError('warn', `[Connection Error]`, error, context, severity, details);

        let userMessage = `Connection issue: ${errorMessage}`;
        let toastType: 'error' | 'warning' | 'info' = 'warning';

        switch (severity) {
            case ErrorSeverity.LOW:
                userMessage = `Minor connection issue. Retrying...`; // More user-friendly
                toastType = 'info';
                break;
            case ErrorSeverity.MEDIUM:
                 userMessage = `Connection problem detected. The application may be temporarily unresponsive.`;
                 toastType = 'warning';
                 break;
            case ErrorSeverity.HIGH:
            case ErrorSeverity.FATAL: // Treat fatal connection errors similarly for user notification
                 userMessage = `Connection failed. Please check your network or try again later. ${errorMessage}`;
                 toastType = 'error';
                 break;
        }
        this.notifyUser(toastType, userMessage, severity);
    }

    /**
     * Handles authentication-related errors (login failure, token expiry/refresh failure).
     * @param error - The error object or message string.
     * @param severity - Optional severity (default: HIGH).
     * @param context - Optional context string (e.g., 'Login', 'TokenRefresh').
     * @param details - Optional additional details.
     */
    public handleAuthError(
        error: Error | string,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        context: string = 'authentication',
        details?: ErrorDetails
    ): void {
        const errorMessage = typeof error === 'string' ? error : error.message;
        // Log auth errors as 'error' level generally
        this.logError('error', `[Auth Error]`, error, context, severity, details);

         let userMessage = `Authentication failed: ${errorMessage}`;
         // Don't show overly technical messages like "No refresh token" to user
         if (errorMessage.includes('No refresh token')) {
            userMessage = 'Your session may have expired. Please log in again.';
         } else if (errorMessage.includes('Session refresh failed') || errorMessage.includes('Token refresh API call failed')) {
             userMessage = 'Your session could not be refreshed. Please log in again.';
         }


        // Auth errors are usually high severity for user notification
        this.notifyUser('error', userMessage, severity);
        // Consider triggering logout logic here or in the calling service based on the error/severity
    }

    /**
     * Handles data processing errors or errors reported by the API within a successful HTTP response.
     * @param error - The error object or message string (often from API response).
     * @param severity - Optional severity (default: MEDIUM).
     * @param context - Optional context string (e.g., 'OrderParsing', 'ApiResponse').
     * @param details - Optional additional details.
     */
    public handleDataError(
        error: Error | string,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: string = 'data',
        details?: ErrorDetails
    ): void {
        const errorMessage = typeof error === 'string' ? error : error.message;
         // Log data errors typically as 'warn' unless fatal
         const logLevel = (severity === ErrorSeverity.HIGH || severity === ErrorSeverity.FATAL) ? 'error' : 'warn';
        this.logError(logLevel, `[Data Error]`, error, context, severity, details);


        let userMessage = `Data processing error: ${errorMessage}`;
        let toastType: 'error' | 'warning' | 'info' = 'warning';

        switch (severity) {
             case ErrorSeverity.LOW:
                 userMessage = `Minor data issue: ${errorMessage}`;
                 toastType = 'info';
                 break;
             case ErrorSeverity.MEDIUM:
                 userMessage = `Could not process some data: ${errorMessage}`;
                 toastType = 'warning';
                 break;
             case ErrorSeverity.HIGH:
             case ErrorSeverity.FATAL:
                  userMessage = `Critical data error: ${errorMessage}`;
                  toastType = 'error';
                  break;
        }
        this.notifyUser(toastType, userMessage, severity);
    }

     /**
     * Handles generic or unexpected application errors (e.g., caught exceptions).
     * @param error - The error object or message string.
     * @param severity - Optional severity (default: HIGH).
     * @param context - Optional context string (e.g., 'ComponentRender', 'WebSocketCallback').
     * @param details - Optional additional details.
     */
    public handleGenericError(
        error: Error | string,
        severity: ErrorSeverity = ErrorSeverity.HIGH, // Default to high for unknowns
        context: string = 'application',
        details?: ErrorDetails
    ): void {
        const errorMessage = typeof error === 'string' ? error : error.message;
        // Log generic errors as 'error' level
        this.logError('error', `[Generic Error]`, error, context, severity, details);

        // Provide a generic message to the user for higher severity errors
        // For lower severity, maybe show more detail if safe
        let userMessage = 'An unexpected error occurred. Please try refreshing the page or contact support if the issue persists.';
        if (severity === ErrorSeverity.LOW || severity === ErrorSeverity.MEDIUM) {
            userMessage = `An issue occurred: ${errorMessage}`;
        }

        this.notifyUser('error', userMessage, severity);
    }
}