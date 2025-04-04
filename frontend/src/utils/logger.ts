// src/utils/logger.ts
export class Logger {
  private static instance: Logger;

  // Constructor is private for singleton
  private constructor() {}

  // Public method to get the singleton instance
  public static getInstance(): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger();
    }
    return Logger.instance;
  }

  // Simple console logging methods - NO createChild method
  info(message: string, context?: any): void {
    console.log(JSON.stringify({
      level: 'INFO',
      message,
      context: context !== undefined ? context : 'NoContext', // Ensure context exists
      timestamp: new Date().toISOString()
    }));
  }

  error(message: string, context?: any): void {
    console.error(JSON.stringify({
      level: 'ERROR',
      message,
      context: context !== undefined ? context : 'NoContext',
      timestamp: new Date().toISOString()
    }));
  }

  warn(message: string, context?: any): void {
    console.warn(JSON.stringify({
      level: 'WARN',
      message,
      context: context !== undefined ? context : 'NoContext',
      timestamp: new Date().toISOString()
    }));
  }

  // Example of how createChild *could* be implemented if needed later
  // public createChild(childName: string): Logger {
  //   // This basic version just returns the same instance
  //   // A more complex version could prefix messages
  //   console.log(`Child logger created: ${childName}`); // Log creation
  //   return this;
  // }
}

