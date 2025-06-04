// src/utils/enhanced-logger.ts
// Define log levels and their priority (lower number = higher priority)
export var LogLevel;
(function (LogLevel) {
    LogLevel[LogLevel["DEBUG"] = 0] = "DEBUG";
    LogLevel[LogLevel["INFO"] = 1] = "INFO";
    LogLevel[LogLevel["WARN"] = 2] = "WARN";
    LogLevel[LogLevel["ERROR"] = 3] = "ERROR";
    LogLevel[LogLevel["NONE"] = 4] = "NONE"; // Special level to disable logging below this
})(LogLevel || (LogLevel = {}));
// Default configuration, potentially overridden during initialization
const DEFAULT_CONFIG = {
    minLevel: LogLevel.INFO, // Default level
    structured: false, // Default to human-readable logs
    includeTimestamp: true,
    environment: (process.env.NODE_ENV || 'development'),
    additionalMetadata: {
    // Example: appName: 'TradingApp'
    // Example: appVersion: process.env.REACT_APP_VERSION || 'unknown'
    }
};
const LEVEL_CONFIG = {
    [LogLevel.DEBUG]: { consoleMethod: 'debug', indicator: '[DEBUG]' },
    [LogLevel.INFO]: { consoleMethod: 'info', indicator: '[INFO]' },
    [LogLevel.WARN]: { consoleMethod: 'warn', indicator: '[WARN]' },
    [LogLevel.ERROR]: { consoleMethod: 'error', indicator: '[ERROR]' },
    [LogLevel.NONE]: { consoleMethod: 'log', indicator: '' } // Should not be used for logging
};
// Make sure the class itself is exported
export class EnhancedLogger {
    // Constructor sets the name and merges configuration
    constructor(name = 'root', config) {
        this.name = name;
        // Merge provided config with defaults
        this.config = {
            ...DEFAULT_CONFIG,
            ...config
        };
        // --- Environment-specific level adjustments ---
        // Automatically set DEBUG level in development if not overridden
        if (this.config.environment === 'development' && (!config || config.minLevel === undefined)) {
            this.config.minLevel = LogLevel.DEBUG;
        }
    }
    // --- Singleton Access ---
    /**
     * Gets the singleton root logger instance.
     * Initializes it with optional configuration on the first call.
     * @param config - Optional configuration for the root logger (applied only on first call).
     * @returns The root EnhancedLogger instance.
     */
    static getInstance(config) {
        if (!EnhancedLogger.rootLogger) {
            EnhancedLogger.rootLogger = new EnhancedLogger('root', config);
        }
        else if (config && EnhancedLogger.rootLogger) {
            // Log warning if trying to reconfigure root logger after initialization
            EnhancedLogger.rootLogger.warn("Root logger already initialized. Reconfiguration attempt ignored.");
        }
        return EnhancedLogger.rootLogger;
    }
    // --- Configuration ---
    /**
     * Overrides the current configuration of this logger instance.
     * @param config - Partial configuration object to merge.
     */
    setConfig(config) {
        const oldLevel = this.config.minLevel;
        this.config = { ...this.config, ...config };
        if (oldLevel !== this.config.minLevel) {
            // Use debug level for internal logger messages
            this.log(LogLevel.DEBUG, `Log level changed to ${LogLevel[this.config.minLevel]}`);
        }
    }
    /** Gets the current minimum log level. */
    getMinLevel() {
        return this.config.minLevel;
    }
    /** Getter to access config if needed (e.g., for testing or conditional logic) */
    get configGetter() {
        return this.config;
    }
    // --- Child Loggers ---
    /**
     * Creates a child logger instance with a hierarchical name (e.g., "root:AuthService").
     * Child logger inherits the parent's configuration but can be overridden.
     * @param childName - The name suffix for the child logger.
     * @param configOverride - Optional configuration specific to the child logger.
     * @returns A new EnhancedLogger instance.
     */
    createChild(childName, configOverride) {
        const fullName = this.name === 'root' ? childName : `<span class="math-inline">\{this\.name\}\:</span>{childName}`;
        // Create new instance inheriting parent config, then applying overrides
        const childLogger = new EnhancedLogger(fullName, {
            ...this.config, // Inherit parent config
            ...configOverride // Apply child-specific overrides
        });
        this.log(LogLevel.DEBUG, `Created child logger: ${fullName}`); // Log child creation at debug level
        return childLogger;
    }
    // --- Logging Methods ---
    /** Logs a DEBUG message if the configured level allows it. */
    debug(message, context) {
        this.log(LogLevel.DEBUG, message, context);
    }
    /** Logs an INFO message if the configured level allows it. */
    info(message, context) {
        this.log(LogLevel.INFO, message, context);
    }
    /** Logs a WARN message if the configured level allows it. */
    warn(message, context) {
        this.log(LogLevel.WARN, message, context);
    }
    /** Logs an ERROR message if the configured level allows it. */
    error(message, context) {
        this.log(LogLevel.ERROR, message, context);
    }
    /**
     * Logs an Error object with its message and stack trace at the ERROR level.
     * @param error - The Error object to log.
     * @param context - Optional additional context.
     */
    logError(error, context) {
        // Ensure context is an object for consistent merging
        const errorContext = typeof context === 'object' && context !== null ? context : {};
        this.log(LogLevel.ERROR, error.message, {
            ...errorContext, // Spread existing context first
            errorName: error.name,
            // Include stack trace, potentially truncated
            stack: error.stack?.split('\n').slice(0, 7).join('\n') // Limit stack trace
        });
    }
    // --- Core Log Method ---
    /**
     * The main private logging method. Checks level and formats output.
     * @param level - The LogLevel of the message.
     * @param message - The main log message string.
     * @param context - Optional context object or value.
     */
    log(level, message, context) {
        // Skip logging if the message level is below the configured minimum level
        if (level < this.config.minLevel || level === LogLevel.NONE)
            return; // Also skip NONE
        // Check if console exists and the method is available (for non-standard environments)
        if (typeof console === 'undefined' || typeof console[LEVEL_CONFIG[level].consoleMethod] !== 'function') {
            return;
        }
        const { consoleMethod, indicator } = LEVEL_CONFIG[level];
        const timestamp = this.config.includeTimestamp ? new Date().toISOString() : undefined;
        if (this.config.structured) {
            // --- Structured JSON Output ---
            try {
                const logEntry = {
                    timestamp,
                    level: LogLevel[level], // Log level as string name
                    logger: this.name,
                    message,
                    // Include context only if it's provided and not undefined
                    ...(context !== undefined && { context }),
                    // Include additional metadata if configured
                    ...this.config.additionalMetadata
                };
                // Output the entire log entry as a JSON string
                console[consoleMethod](JSON.stringify(logEntry));
            }
            catch (jsonError) {
                // Fallback if JSON.stringify fails (e.g., circular references in context)
                console.error(`[Logger Error] Failed to stringify structured log for ${this.name}: ${jsonError.message}`, { originalMessage: message });
            }
        }
        else {
            // --- Human-Readable Output ---
            const timePrefix = timestamp ? `[${timestamp.slice(11, 23)}] ` : ''; // Include milliseconds
            const namePrefix = `[${this.name}] `;
            const levelIndicator = `${indicator} `;
            const formattedMessage = `<span class="math-inline">\{timePrefix\}</span>{levelIndicator}<span class="math-inline">\{namePrefix\}</span>{message}`;
            // Log message and context separately if context exists
            /*
            if (context !== undefined) {
                console[consoleMethod](formattedMessage, context);
            } else {
                console[consoleMethod](formattedMessage);
            }
            */
        }
    }
    // --- Utility Methods ---
    /**
     * Utility function to track the execution time of an async function.
     * Logs the duration at DEBUG level.
     * @param operationName - A descriptive name for the operation being timed.
     * @param fn - The asynchronous function to execute and time.
     * @returns The result of the executed function `fn`.
     */
    async trackTime(operationName, fn) {
        const start = performance.now();
        // Log start only if DEBUG level is enabled
        if (this.config.minLevel <= LogLevel.DEBUG) {
            this.debug(`Starting operation: ${operationName}`);
        }
        try {
            return await fn();
        }
        finally {
            const duration = performance.now() - start;
            // Log end only if DEBUG level is enabled
            if (this.config.minLevel <= LogLevel.DEBUG) {
                this.debug(`Finished operation: <span class="math-inline">\{operationName\} \(</span>{duration.toFixed(2)}ms)`);
            }
        }
    }
}
