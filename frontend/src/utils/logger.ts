// src/utils/logger.ts
export class Logger {
  private static instance: Logger;
  private prefix: string | null = null; // Store prefix

  // Private constructor for internal use (child creation)
  private constructor(prefix?: string) {
      this.prefix = prefix || null;
  }

  // Public method to get the singleton root instance
  public static getInstance(): Logger {
      if (!Logger.instance) {
          Logger.instance = new Logger();
      }
      return Logger.instance;
  }

  // Add the debug method
  debug(message: string, context?: any): void {
    const logMessage = this.prefix ? `${this.prefix} ${message}` : message;
    // You might want to conditionally log debug messages, e.g., only in development
    // if (config.environment === 'development') {
        console.debug(JSON.stringify({ // Use console.debug
            level: 'DEBUG',
            message: logMessage,
            context: context !== undefined ? context : 'NoContext',
            timestamp: new Date().toISOString()
        }));
    // }
  }

  // Create a new Logger instance with a combined prefix
  public createChild(childName: string): Logger {
      const newPrefix = this.prefix ? `<span class="math-inline">\{this\.prefix\}\[</span>{childName}]` : `[${childName}]`;
      // Create a new instance, not returning 'this'
      return new Logger(newPrefix);
  }

  // Add prefix to log methods
  info(message: string, context?: any): void {
      const logMessage = this.prefix ? `${this.prefix} ${message}` : message;
      console.log(JSON.stringify({
          level: 'INFO',
          message: logMessage, // Use prefixed message
          context: context !== undefined ? context : 'NoContext',
          timestamp: new Date().toISOString()
      }));
  }

  error(message: string, context?: any): void {
       const logMessage = this.prefix ? `${this.prefix} ${message}` : message;
       console.error(JSON.stringify({
           level: 'ERROR',
           message: logMessage, // Use prefixed message
           context: context !== undefined ? context : 'NoContext',
           timestamp: new Date().toISOString()
       }));
  }

  warn(message: string, context?: any): void {
      const logMessage = this.prefix ? `${this.prefix} ${message}` : message;
      console.warn(JSON.stringify({
          level: 'WARN',
          message: logMessage, // Use prefixed message
          context: context !== undefined ? context : 'NoContext',
          timestamp: new Date().toISOString()
      }));
  }
}