import { TokenManager } from '../services/auth/token-manager';
export interface RequestOptions extends RequestInit {
    skipAuth?: boolean;
    retries?: number;
    suppressErrorToast?: boolean;
    customErrorMessage?: string;
    context?: string;
}
export declare class HttpClient {
    private readonly logger;
    private readonly baseUrl;
    private readonly tokenManager;
    private readonly maxRetries;
    constructor(tokenManager: TokenManager);
    get<T>(endpoint: string, options?: RequestOptions): Promise<T>;
    post<T>(endpoint: string, data?: any, options?: RequestOptions): Promise<T>;
    put<T>(endpoint: string, data?: any, options?: RequestOptions): Promise<T>;
    delete<T>(endpoint: string, options?: RequestOptions): Promise<T>;
    postMultipart<T>(endpoint: string, formData: FormData, options?: RequestOptions): Promise<T>;
    private request;
    private handleHttpErrorResponse;
    private getCsrfHeader;
    private handleNetworkOrFetchError;
}
