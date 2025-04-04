// src/utils/error-handler.ts
import { toastService, ToastService } from '../services/notification/toast-service'; // Import type and instance
import { Logger } from './logger';

// ErrorSeverity enum remains the same
export enum ErrorSeverity {
    LOW = 'low',
    MEDIUM = 'medium',
    HIGH = 'high',
    FATAL = 'fatal'
}

/**
 * Handles application errors by logging and displaying notifications.
 * Designed to be instantiated and injected into services.
 */
export class ErrorHandler {
    private readonly logger: Logger;
    private readonly toastService: ToastService; // Use injected toast service instance

    /**
     * Creates an instance of ErrorHandler.
     * @param logger - The Logger instance for logging errors.
     * @param toastServiceInstance - The ToastService instance for displaying notifications.
     */
    constructor(logger: Logger, toastServiceInstance: ToastService) {
        // Create a child logger specific to the ErrorHandler instance
        this.logger = logger.createChild('ErrorHandler');
        this.toastService = toastServiceInstance;
        this.logger.info('ErrorHandler instance created.');
    }

    /**
     * Handles connection-related errors.
     * @param error - The error object or message string.
     * @param severity - The severity level of the error.
     * @param context - A string providing context about where the error occurred.
     */
    public handleConnectionError(
        error: Error | string,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: string = 'connection'
    ): void {
        const errorMessage = typeof error === 'string' ? error : error.message;
        const errorDetails = typeof error === 'string' ? { message: error } : error;

        this.logger.error(`[${context}] error: ${errorMessage}`, { error: errorDetails, severity });

        switch (severity) {
            case ErrorSeverity.LOW:
                this.toastService.info(`Connection issue: ${errorMessage}`, 5000);
                break;
            case ErrorSeverity.MEDIUM:
                this.toastService.warning(`Connection problem: ${errorMessage}`, 7000);
                break;
            case ErrorSeverity.HIGH:
                this.toastService.error(`Connection error: ${errorMessage}`, 10000);
                break;
            case ErrorSeverity.FATAL:
                this.toastService.error(`Critical connection failure: ${errorMessage}`, 0); // No auto-dismiss
                // Potentially trigger application shutdown or redirect here for FATAL errors
                break;
        }
    }

    /**
     * Handles authentication-related errors.
     * @param error - The error object or message string.
     * @param severity - The severity level of the error.
     * @param context - A string providing context about where the error occurred.
     */
    public handleAuthError(
        error: Error | string,
        severity: ErrorSeverity = ErrorSeverity.HIGH,
        context: string = 'authentication'
    ): void {
        const errorMessage = typeof error === 'string' ? error : error.message;
        const errorDetails = typeof error === 'string' ? { message: error } : error;

        this.logger.error(`[${context}] error: ${errorMessage}`, { error: errorDetails, severity });

        switch (severity) {
            case ErrorSeverity.MEDIUM:
                this.toastService.warning(`Authentication issue: ${errorMessage}`, 7000);
                break;
            case ErrorSeverity.HIGH:
            case ErrorSeverity.FATAL: // Treat FATAL auth errors similarly to HIGH
                this.toastService.error(`Authentication failed: ${errorMessage}`, 10000);
                // Consider triggering logout automatically here for HIGH/FATAL auth errors
                break;
            default: // Handle LOW severity if needed, otherwise default to warning
                this.toastService.warning(`Authentication issue: ${errorMessage}`, 5000);
        }
    }

    /**
     * Handles data processing or API data errors.
     * @param error - The error object or message string.
     * @param severity - The severity level of the error.
     * @param context - A string providing context about where the error occurred.
     */
    public handleDataError(
        error: Error | string,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: string = 'data'
    ): void {
        const errorMessage = typeof error === 'string' ? error : error.message;
        const errorDetails = typeof error === 'string' ? { message: error } : error;

        this.logger.error(`[${context}] error: ${errorMessage}`, { error: errorDetails, severity });

        switch (severity) {
            case ErrorSeverity.LOW:
                this.toastService.info(`Data issue: ${errorMessage}`, 5000);
                break;
            case ErrorSeverity.MEDIUM:
                this.toastService.warning(`Data problem: ${errorMessage}`, 7000);
                break;
            case ErrorSeverity.HIGH:
            case ErrorSeverity.FATAL: // Treat FATAL data errors similarly to HIGH
                this.toastService.error(`Data error: ${errorMessage}`, 10000);
                break;
        }
    }

     /**
     * Handles generic or unexpected application errors.
     * @param error - The error object or message string.
     * @param severity - The severity level of the error.
     * @param context - A string providing context about where the error occurred.
     */
    public handleGenericError(
        error: Error | string,
        severity: ErrorSeverity = ErrorSeverity.HIGH, // Default to high for unknowns
        context: string = 'application'
    ): void {
        const errorMessage = typeof error === 'string' ? error : error.message;
        const errorDetails = typeof error === 'string' ? { message: error } : error;

        this.logger.error(`[${context}] UNEXPECTED error: ${errorMessage}`, { error: errorDetails, severity });

        // Use a generic error message for the user unless severity is low
        if (severity !== ErrorSeverity.LOW) {
            this.toastService.error(`An unexpected error occurred. Please try again later.`, 10000);
        } else {
             this.toastService.warning(`A minor issue occurred: ${errorMessage}`, 5000);
        }
    }
}

// How to initialize and use (e.g., in your main application setup):
// import { Logger } from './utils/logger';
// import { toastService } from './services/notification/toast-service';
// import { ErrorHandler } from './utils/error-handler';
//
// const logger = Logger.getInstance();
// const errorHandler = new ErrorHandler(logger, toastService); // Pass logger and toast service instance
//
// // Later in other services:
// // constructor(..., errorHandler: ErrorHandler) { this.errorHandler = errorHandler; }
// // this.errorHandler.handleConnectionError(...);
