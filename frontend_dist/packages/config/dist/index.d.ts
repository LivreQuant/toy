import { LogLevel } from '../utils/enhanced-logger';
interface AppConfig {
    apiBaseUrl: string;
    wsBaseUrl: string;
    environment: 'development' | 'production' | 'test';
    logLevel?: LogLevel;
    secureSockets: boolean;
    reconnection: {
        initialDelayMs: number;
        maxDelayMs: number;
        jitterFactor: number;
        maxAttempts: number;
    };
}
export declare const config: AppConfig;
export {};
