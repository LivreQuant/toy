// src/utils/logging-helpers.ts
import { EnhancedLogger } from './enhanced-logger';

/**
 * Logs the execution time of an async function
 */
export async function logExecutionTime<T>(
  logger: EnhancedLogger,
  operationName: string,
  fn: () => Promise<T>
): Promise<T> {
  const start = performance.now();
  logger.debug(`Starting operation: ${operationName}`);
  
  try {
    return await fn();
  } finally {
    const duration = performance.now() - start;
    logger.debug(`Finished operation: ${operationName} (${duration.toFixed(2)}ms)`);
  }
}

/**
 * Creates log context with standard metadata
 */
export function createLogContext(
  baseContext: Record<string, any> = {},
  extraContext: Record<string, any> = {}
): Record<string, any> {
  return {
    timestamp: new Date().toISOString(),
    ...baseContext,
    ...extraContext
  };
}

/**
 * Decorates a class method to log execution time
 */
export function LogExecutionTime(logger: EnhancedLogger, operationNamePrefix: string = '') {
  return function(
    target: any,
    propertyKey: string,
    descriptor: PropertyDescriptor
  ) {
    const originalMethod = descriptor.value;
    
    descriptor.value = async function(...args: any[]) {
      const operationName = `${operationNamePrefix}${propertyKey}`;
      return logExecutionTime(logger, operationName, () => originalMethod.apply(this, args));
    };
    
    return descriptor;
  };
}

/**
 * Formats an error for logging
 */
export function formatError(error: any): Record<string, any> {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message,
      stack: error.stack?.split('\n').slice(0, 5).join('\n')
    };
  }
  
  return { error: String(error) };
}

/**
 * Creates a scoped logger with additional context
 */
export function createScopedLogger(
  baseLogger: EnhancedLogger,
  scope: string,
  baseContext: Record<string, any> = {}
): {
  debug: (message: string, context?: Record<string, any>) => void;
  info: (message: string, context?: Record<string, any>) => void;
  warn: (message: string, context?: Record<string, any>) => void;
  error: (message: string, context?: Record<string, any>) => void;
} {
  return {
    debug: (message, context) => baseLogger.debug(`[${scope}] ${message}`, createLogContext(baseContext, context)),
    info: (message, context) => baseLogger.info(`[${scope}] ${message}`, createLogContext(baseContext, context)),
    warn: (message, context) => baseLogger.warn(`[${scope}] ${message}`, createLogContext(baseContext, context)),
    error: (message, context) => baseLogger.error(`[${scope}] ${message}`, createLogContext(baseContext, context))
  };
}