class Logger {
    private static instance: Logger;
    
    private constructor() {}
  
    public static getInstance(): Logger {
      if (!Logger.instance) {
        Logger.instance = new Logger();
      }
      return Logger.instance;
    }
  
    info(message: string, context?: any): void {
      console.log(JSON.stringify({
        level: 'INFO',
        message,
        context,
        timestamp: new Date().toISOString()
      }));
    }
  
    error(message: string, context?: any): void {
      console.error(JSON.stringify({
        level: 'ERROR',
        message,
        context,
        timestamp: new Date().toISOString()
      }));
    }
  
    warn(message: string, context?: any): void {
      console.warn(JSON.stringify({
        level: 'WARN',
        message,
        context,
        timestamp: new Date().toISOString()
      }));
    }
  }