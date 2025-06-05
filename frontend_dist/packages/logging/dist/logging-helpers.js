/**
 * Logs the execution time of an async function
 */
export async function logExecutionTime(logger, operationName, fn) {
    const start = performance.now();
    logger.debug(`Starting operation: ${operationName}`);
    try {
        return await fn();
    }
    finally {
        const duration = performance.now() - start;
        logger.debug(`Finished operation: ${operationName} (${duration.toFixed(2)}ms)`);
    }
}
/**
 * Creates log context with standard metadata
 */
export function createLogContext(baseContext = {}, extraContext = {}) {
    return Object.assign(Object.assign({ timestamp: new Date().toISOString() }, baseContext), extraContext);
}
/**
 * Decorates a class method to log execution time
 */
export function LogExecutionTime(logger, operationNamePrefix = '') {
    return function (target, propertyKey, descriptor) {
        const originalMethod = descriptor.value;
        descriptor.value = async function (...args) {
            const operationName = `${operationNamePrefix}${propertyKey}`;
            return logExecutionTime(logger, operationName, () => originalMethod.apply(this, args));
        };
        return descriptor;
    };
}
/**
 * Formats an error for logging
 */
export function formatError(error) {
    var _a;
    if (error instanceof Error) {
        return {
            name: error.name,
            message: error.message,
            stack: (_a = error.stack) === null || _a === void 0 ? void 0 : _a.split('\n').slice(0, 5).join('\n')
        };
    }
    return { error: String(error) };
}
/**
 * Creates a scoped logger with additional context
 */
export function createScopedLogger(baseLogger, scope, baseContext = {}) {
    return {
        debug: (message, context) => baseLogger.debug(`[${scope}] ${message}`, createLogContext(baseContext, context)),
        info: (message, context) => baseLogger.info(`[${scope}] ${message}`, createLogContext(baseContext, context)),
        warn: (message, context) => baseLogger.warn(`[${scope}] ${message}`, createLogContext(baseContext, context)),
        error: (message, context) => baseLogger.error(`[${scope}] ${message}`, createLogContext(baseContext, context))
    };
}
