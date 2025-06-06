export interface AppConfig {
    apiBaseUrl: string;
    wsBaseUrl: string;
    environment: string;
    reconnection: {
        initialDelayMs: number;
        maxDelayMs: number;
        jitterFactor: number;
        maxAttempts: number;
    };
}
export declare const config: AppConfig;
export declare const API_BASE_URL: string;
export declare const WS_BASE_URL: string;
export declare const ENVIRONMENT: string;
export declare const RECONNECTION_CONFIG: {
    initialDelayMs: number;
    maxDelayMs: number;
    jitterFactor: number;
    maxAttempts: number;
};
export default config;
