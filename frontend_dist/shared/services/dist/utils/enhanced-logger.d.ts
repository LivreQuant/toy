export declare enum LogLevel {
    DEBUG = 0,
    INFO = 1,
    WARN = 2,
    ERROR = 3,
    NONE = 4
}
export interface LoggerConfig {
    minLevel: LogLevel;
    structured: boolean;
    includeTimestamp: boolean;
    environment: 'development' | 'production' | 'test';
    additionalMetadata?: Record<string, any>;
}
export declare class EnhancedLogger {
    private config;
    private readonly name;
    private static rootLogger;
    constructor(name?: string, config?: Partial<LoggerConfig>);
    /**
     * Gets the singleton root logger instance.
     * Initializes it with optional configuration on the first call.
     * @param config - Optional configuration for the root logger (applied only on first call).
     * @returns The root EnhancedLogger instance.
     */
    static getInstance(config?: Partial<LoggerConfig>): EnhancedLogger;
    /**
     * Overrides the current configuration of this logger instance.
     * @param config - Partial configuration object to merge.
     */
    setConfig(config: Partial<LoggerConfig>): void;
    /** Gets the current minimum log level. */
    getMinLevel(): LogLevel;
    /** Getter to access config if needed (e.g., for testing or conditional logic) */
    get configGetter(): Readonly<LoggerConfig>;
    /**
     * Creates a child logger instance with a hierarchical name (e.g., "root:AuthService").
     * Child logger inherits the parent's configuration but can be overridden.
     * @param childName - The name suffix for the child logger.
     * @param configOverride - Optional configuration specific to the child logger.
     * @returns A new EnhancedLogger instance.
     */
    createChild(childName: string, configOverride?: Partial<LoggerConfig>): EnhancedLogger;
    /** Logs a DEBUG message if the configured level allows it. */
    debug(message: string, context?: any): void;
    /** Logs an INFO message if the configured level allows it. */
    info(message: string, context?: any): void;
    /** Logs a WARN message if the configured level allows it. */
    warn(message: string, context?: any): void;
    /** Logs an ERROR message if the configured level allows it. */
    error(message: string, context?: any): void;
    /**
     * Logs an Error object with its message and stack trace at the ERROR level.
     * @param error - The Error object to log.
     * @param context - Optional additional context.
     */
    logError(error: Error, context?: any): void;
    /**
     * The main private logging method. Checks level and formats output.
     * @param level - The LogLevel of the message.
     * @param message - The main log message string.
     * @param context - Optional context object or value.
     */
    private log;
    /**
     * Utility function to track the execution time of an async function.
     * Logs the duration at DEBUG level.
     * @param operationName - A descriptive name for the operation being timed.
     * @param fn - The asynchronous function to execute and time.
     * @returns The result of the executed function `fn`.
     */
    trackTime<T>(operationName: string, fn: () => Promise<T>): Promise<T>;
}
