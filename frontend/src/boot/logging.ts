// src/boot/logging.ts (Corrected Import)
// Use named imports now
import { EnhancedLogger, LogLevel, LoggerConfig } from '../utils/enhanced-logger';
import { config } from '../config'; // Your app config

let rootLoggerInstance: EnhancedLogger | null = null;

export function initializeLogging(): void {
  // Prevent double initialization
  if (rootLoggerInstance) {
    rootLoggerInstance.warn("initializeLogging called more than once.");
    return;
  }

  const environment = config.environment;

  // Determine initial log level
  let minLevel = LogLevel.INFO; // Default
  if (environment === 'development') {
    minLevel = LogLevel.DEBUG;
  } else if (environment === 'test') {
    minLevel = LogLevel.WARN; // Or LogLevel.NONE
  }

  // Check localStorage override
  try {
    const storedLevel = localStorage.getItem('log_level');
    const parsedLevel = storedLevel ? parseInt(storedLevel, 10) : NaN;
    if (!isNaN(parsedLevel) && LogLevel[parsedLevel] !== undefined) {
      minLevel = parsedLevel;
    }
  } catch (e) {
    console.error("Error reading log_level from localStorage", e);
  }

  // Base configuration
  const loggerConfig: Partial<LoggerConfig> = {
      minLevel,
      structured: environment === 'production',
      environment: environment as 'development' | 'production' | 'test',
      additionalMetadata: {
          // appVersion: '1.0.1', // Example
      }
  };

  // Get/Initialize the root logger instance using the static method
  rootLoggerInstance = EnhancedLogger.getInstance(loggerConfig);

  // Log initialization *using the instance*
  rootLoggerInstance.info(`Logging initialized for ${config.environment}`, {
    level: LogLevel[minLevel],
    structured: rootLoggerInstance.configGetter.structured
  });

  // Setup global error handlers *after* instance is created
  window.onerror = (message, source, lineno, colno, error) => {
    // Use the instance to log
    rootLoggerInstance?.error('Unhandled window error', {
      message,
      source,
      location: `${lineno}:${colno}`,
      error: error ? {
        name: error.name,
        message: error.message,
        stack: error.stack?.substring(0, 500)
      } : undefined
    });
    return false;
  };

  window.onunhandledrejection = (event) => {
    const reason = event.reason;
    // Use the instance to log
    rootLoggerInstance?.error('Unhandled promise rejection', {
      reason: reason instanceof Error ? {
        name: reason.name,
        message: reason.message,
        stack: reason.stack?.substring(0, 500)
      } : reason
    });
  };
}

/**
 * Utility function to easily get a child logger instance from the root logger.
 * Ensures the root logger is initialized before creating children.
 * @param name - The name for the child logger (e.g., 'AuthService', 'MyComponent').
 * @returns An EnhancedLogger instance.
 * @throws Error if initializeLogging() has not been called.
 */
export function getLogger(name: string): EnhancedLogger {
  if (!rootLoggerInstance) {
    // Fallback: Initialize if not already done? Or throw?
    // Throwing is safer to enforce initialization order.
    throw new Error("Logging not initialized. Call initializeLogging() first.");
    // Or initialize here (less ideal as it might miss initial config):
    // initializeLogging();
    // return rootLoggerInstance!.createChild(name);
  }
  return rootLoggerInstance.createChild(name);
}