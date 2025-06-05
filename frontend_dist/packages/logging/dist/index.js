// src/boot/logging.ts
import { EnhancedLogger, LogLevel } from '../utils/enhanced-logger';
import { config } from '../config'; // Your app config
let rootLoggerInstance = null;
export function initializeLogging() {
    // Prevent double initialization
    if (rootLoggerInstance) {
        // Use console.warn directly in case the logger itself is broken
        console.warn("initializeLogging called more than once.");
        return;
    }
    const environment = config.environment;
    // Determine initial log level
    let minLevel = LogLevel.INFO; // Default
    if (environment === 'development') {
        minLevel = LogLevel.DEBUG;
    }
    else if (environment === 'test') {
        minLevel = LogLevel.WARN; // Or LogLevel.NONE
    }
    // Check localStorage override
    try {
        const storedLevel = localStorage.getItem('log_level');
        const parsedLevel = storedLevel ? parseInt(storedLevel, 10) : NaN;
        if (!isNaN(parsedLevel) && LogLevel[parsedLevel] !== undefined) {
            minLevel = parsedLevel;
        }
    }
    catch (e) {
        console.error("Error reading log_level from localStorage", e);
    }
    // Base configuration
    const loggerConfig = {
        minLevel,
        structured: environment === 'production',
        environment: environment,
        additionalMetadata: {
        // appVersion: '1.0.1', // Example
        }
    };
    // Get/Initialize the root logger instance using the static method
    rootLoggerInstance = EnhancedLogger.getInstance(config);
    // Log initialization *using the instance*
    rootLoggerInstance.info(`Logging initialized for ${config.environment}`, {
        level: LogLevel[minLevel],
        structured: rootLoggerInstance.configGetter.structured
    });
    // Setup global error handlers *after* instance is created
    window.onerror = (message, source, lineno, colno, error) => {
        var _a;
        // Use the instance to log
        rootLoggerInstance === null || rootLoggerInstance === void 0 ? void 0 : rootLoggerInstance.error('Unhandled window error', {
            message,
            source,
            location: `<span class="math-inline">\{lineno\}\:</span>{colno}`,
            error: error ? {
                name: error.name,
                message: error.message,
                stack: (_a = error.stack) === null || _a === void 0 ? void 0 : _a.substring(0, 500)
            } : undefined
        });
        return false; // Prevent default browser handling
    };
    window.onunhandledrejection = (event) => {
        var _a;
        const reason = event.reason;
        // Use the instance to log
        rootLoggerInstance === null || rootLoggerInstance === void 0 ? void 0 : rootLoggerInstance.error('Unhandled promise rejection', {
            reason: reason instanceof Error ? {
                name: reason.name,
                message: reason.message,
                stack: (_a = reason.stack) === null || _a === void 0 ? void 0 : _a.substring(0, 500)
            } : reason
        });
    };
}
/**
 * Utility function to easily get a child logger instance from the root logger.
 * Ensures the root logger is initialized before creating children.
 * @param name - The name for the child logger (e.g., 'AuthService', 'MyComponent').
 * @returns An EnhancedLogger instance.
 */
export function getLogger(name) {
    if (!rootLoggerInstance) {
        // FIX: Add fallback initialization with a warning
        console.warn(`Logging not initialized when getLogger('${name}') was called. Initializing automatically. Check application startup order in index.tsx.`);
        initializeLogging(); // Attempt to initialize
        // If initialization failed somehow, rootLoggerInstance could still be null
        if (!rootLoggerInstance) {
            // Fallback to console if initialization fails critically
            console.error(`CRITICAL: Failed to initialize root logger even during fallback for '${name}'. Returning basic console logger.`);
            // Return a dummy logger that uses console to prevent further crashes
            const dummyConfig = { minLevel: LogLevel.DEBUG, structured: false, includeTimestamp: true, environment: 'development' };
            // Basic implementation matching EnhancedLogger interface
            const dummyLogger = {
                debug: (msg, ctx) => console.debug(`[${name}|DEBUG]`, msg, ctx),
                info: (msg, ctx) => console.info(`[${name}|INFO]`, msg, ctx),
                warn: (msg, ctx) => console.warn(`[${name}|WARN]`, msg, ctx),
                error: (msg, ctx) => console.error(`[${name}|ERROR]`, msg, ctx),
                logError: (err, ctx) => console.error(`[${name}|ERROR]`, err, ctx),
                createChild: (childName) => getLogger(`<span class="math-inline">\{name\}\:</span>{childName}`), // Recursive call with type assertion
                setConfig: () => { },
                getMinLevel: () => LogLevel.DEBUG,
                configGetter: dummyConfig,
                trackTime: async (opName, fn) => { console.debug(`[${name}] Starting: ${opName}`); const r = await fn(); console.debug(`[${name}] Finished: ${opName}`); return r; }
            };
            return dummyLogger; // Use type assertion
        }
    }
    return rootLoggerInstance.createChild(name);
}
