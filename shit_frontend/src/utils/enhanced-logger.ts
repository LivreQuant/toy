// src/utils/enhanced-logger.ts
// Define log levels and their priority
export enum LogLevel {
    DEBUG = 0,
    INFO = 1,
    WARN = 2,
    ERROR = 3,
    NONE = 4 // Special level to disable logging
  }
  
  // Configuration interface for the logger
  export interface LoggerConfig {
    minLevel: LogLevel;
    structured: boolean;
    includeTimestamp: boolean;
    environment: 'development' | 'production' | 'test';
    additionalMetadata?: Record<string, any>;
  }
  
  // Default configuration
  const DEFAULT_CONFIG: LoggerConfig = {
    minLevel: LogLevel.INFO,
    structured: true,
    includeTimestamp: true,
    environment: (process.env.NODE_ENV || 'development') as 'development' | 'production' | 'test',
    additionalMetadata: {
      appVersion: process.env.REACT_APP_VERSION || 'unknown'
    }
  };
  
  // Level-specific configuration
  interface LevelConfig {
    console: 'log' | 'info' | 'warn' | 'error' | 'debug';
    emoji: string;
  }
  
  const LEVEL_CONFIG: Record<LogLevel, LevelConfig> = {
    [LogLevel.DEBUG]: { console: 'debug', emoji: '🔍' },
    [LogLevel.INFO]: { console: 'info', emoji: 'ℹ️' },
    [LogLevel.WARN]: { console: 'warn', emoji: '⚠️' },
    [LogLevel.ERROR]: { console: 'error', emoji: '❌' },
    [LogLevel.NONE]: { console: 'log', emoji: '' }
  };
  
  export class EnhancedLogger {
    private config: LoggerConfig;
    private name: string;
    private static rootLogger: EnhancedLogger;
  
    constructor(name: string = 'root', config?: Partial<LoggerConfig>) {
      this.name = name;
      this.config = {
        ...DEFAULT_CONFIG,
        ...config
      };
  
      // Adjust log level based on environment
      if (this.config.environment === 'production' && this.config.minLevel < LogLevel.INFO) {
        this.config.minLevel = LogLevel.INFO;
      }
    }
  
    // Get the singleton root instance
    public static getInstance(config?: Partial<LoggerConfig>): EnhancedLogger {
      if (!EnhancedLogger.rootLogger) {
        EnhancedLogger.rootLogger = new EnhancedLogger('root', config);
      }
      return EnhancedLogger.rootLogger;
    }
  
    // Override configuration
    setConfig(config: Partial<LoggerConfig>): void {
      this.config = {
        ...this.config,
        ...config
      };
    }
  
    // Create a child logger that inherits parent config
    createChild(childName: string, config?: Partial<LoggerConfig>): EnhancedLogger {
      const fullName = this.name === 'root' ? childName : `${this.name}:${childName}`;
      const childLogger = new EnhancedLogger(fullName, {
        ...this.config,
        ...config
      });
      return childLogger;
    }
  
    // Logging methods
    debug(message: string, context?: any): void {
      this.log(LogLevel.DEBUG, message, context);
    }
  
    info(message: string, context?: any): void {
      this.log(LogLevel.INFO, message, context);
    }
  
    warn(message: string, context?: any): void {
      this.log(LogLevel.WARN, message, context);
    }
  
    error(message: string, context?: any): void {
      this.log(LogLevel.ERROR, message, context);
    }
  
    // Main log method
    private log(level: LogLevel, message: string, context?: any): void {
      // Skip logging if level is below minimum
      if (level < this.config.minLevel) return;
  
      const { console: consoleMethod, emoji } = LEVEL_CONFIG[level];
      const timestamp = this.config.includeTimestamp ? new Date().toISOString() : undefined;
      const logData = {
        level: LogLevel[level],
        logger: this.name,
        message: `${emoji} ${message}`,
        context: context || undefined,
        timestamp,
        ...this.config.additionalMetadata
      };
  
      if (this.config.structured) {
        // Structured output (for JSON parsing tools, etc.)
        console[consoleMethod](JSON.stringify(logData));
      } else {
        // Human-readable format
        const timePrefix = timestamp ? `[${timestamp.slice(11, 19)}] ` : '';
        const namePrefix = `[${this.name}] `;
        const fullMessage = `${timePrefix}${LogLevel[level]} ${namePrefix}${emoji} ${message}`;
        
        if (context) {
          console[consoleMethod](fullMessage, context);
        } else {
          console[consoleMethod](fullMessage);
        }
      }
    }
  
    // Utility function to track method execution time (useful for performance logging)
    async trackTime<T>(name: string, fn: () => Promise<T>): Promise<T> {
      const start = performance.now();
      try {
        return await fn();
      } finally {
        const duration = performance.now() - start;
        this.debug(`${name} completed in ${duration.toFixed(2)}ms`);
      }
    }
  
    // Log application error with stack trace
    logError(error: Error, context?: any): void {
      this.error(error.message, {
        ...(context || {}),
        name: error.name,
        stack: error.stack
      });
    }
  }
  
  // Create and export singleton instance
  const globalLogger = EnhancedLogger.getInstance();
  export default globalLogger;