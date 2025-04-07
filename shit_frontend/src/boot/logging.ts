// src/boot/logging.ts
import globalLogger, { EnhancedLogger, LogLevel } from '../utils/enhanced-logger';
import { config } from '../config';

export function initializeLogging(): void {
  const environment = config.environment;
  
  // Default log levels based on environment
  let minLevel = LogLevel.INFO;
  
  if (environment === 'development') {
    minLevel = LogLevel.DEBUG;
  } else if (environment === 'test') {
    minLevel = LogLevel.WARN;
  }
  
  // Override from localStorage if present (for debugging in production)
  try {
    const storedLevel = localStorage.getItem('log_level');
    if (storedLevel && Object.values(LogLevel).includes(parseInt(storedLevel))) {
      minLevel = parseInt(storedLevel);
    }
  } catch (e) {
    // Ignore localStorage errors
  }
  
  // Configure global logger
  globalLogger.setConfig({
    minLevel,
    structured: environment === 'production', // Structured in prod, readable in dev
    environment: environment as 'development' | 'production' | 'test',
    additionalMetadata: {
      appVersion: process.env.REACT_APP_VERSION || 'unknown',
      buildTimestamp: process.env.REACT_APP_BUILD_TIME || 'unknown'
    }
  });
  
  // Log initial configuration
  globalLogger.info(`Logging initialized`, { 
    level: LogLevel[minLevel],
    environment, 
    structured: environment === 'production' 
  });
  
  // Add global error handling
  window.onerror = (message, source, lineno, colno, error) => {
    globalLogger.error('Unhandled error', {
      message,
      source,
      location: `${lineno}:${colno}`,
      error: error ? {
        name: error.name,
        message: error.message,
        stack: error.stack
      } : undefined
    });
  };
  
  window.onunhandledrejection = (event) => {
    const reason = event.reason;
    globalLogger.error('Unhandled promise rejection', {
      reason: reason instanceof Error ? {
        name: reason.name,
        message: reason.message,
        stack: reason.stack
      } : reason
    });
  };
}

// Export a helper to get logger instances
export function getLogger(name: string): EnhancedLogger {
  return globalLogger.createChild(name);
}