// src/api/http-client.ts
import { TokenManager } from '../services/auth/token-manager';
import { config } from '../config';
import { toastService } from '../services/notification/toast-service';

export interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
  retries?: number;
  suppressErrorToast?: boolean;
  customErrorMessage?: string;
}

export class HttpClient {
  private readonly baseUrl: string;
  private readonly tokenManager: TokenManager;
  private readonly maxRetries: number = 3;
  
  constructor(tokenManager: TokenManager) {
    this.baseUrl = config.apiBaseUrl;
    this.tokenManager = tokenManager;
  }
  
  public async get<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    return this.request<T>('GET', endpoint, undefined, options);
  }
  
  public async post<T>(endpoint: string, data?: any, options: RequestOptions = {}): Promise<T> {
    return this.request<T>('POST', endpoint, data, options);
  }
  
  public async put<T>(endpoint: string, data?: any, options: RequestOptions = {}): Promise<T> {
    return this.request<T>('PUT', endpoint, data, options);
  }
  
  public async delete<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    return this.request<T>('DELETE', endpoint, undefined, options);
  }
  
  private async request<T>(
    method: string, 
    endpoint: string, 
    data?: any, 
    options: RequestOptions = {},
    retryCount = 0
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    // Setup request headers
    const headers = new Headers(options.headers);
    
    // Add auth token if needed
    if (!options.skipAuth) {
      try {
        const token = await this.tokenManager.getAccessToken();
        if (token) {
          headers.set('Authorization', `Bearer ${token}`);
        }
      } catch (authError) {
        this.handleError('Authentication failed', options);
        throw authError;
      }
    }
    
    // Add content type for JSON if not specified
    if (data && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    
    // Build request options
    const requestOptions: RequestInit = {
      ...options,
      method,
      headers,
      body: data ? JSON.stringify(data) : undefined,
      credentials: 'include',
    };
    
    try {
      const response = await fetch(url, requestOptions);
      
      // Handle successful responses
      if (response.ok) {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          return await response.json();
        }
        return {} as T;
      }
      
      // Handle error responses
      return this.handleErrorResponse<T>(
        response, 
        method, 
        endpoint, 
        options, 
        retryCount
      );
      
    } catch (error) {
      return this.handleNetworkError<T>(
        error, 
        method, 
        endpoint, 
        options, 
        retryCount
      );
    }
  }
  
  private async handleErrorResponse<T>(
    response: Response, 
    method: string, 
    endpoint: string, 
    options: RequestOptions,
    retryCount: number
  ): Promise<T> {
    let errorMessage = `HTTP error! status: ${response.status}`;
    
    try {
      // Try to parse error details from response
      const errorData = await response.json();
      errorMessage = errorData.message || errorData.error || errorMessage;
    } catch {
      // Fallback to status text if JSON parsing fails
      errorMessage = response.statusText || errorMessage;
    }
    
    // Handle 401 Unauthorized - attempt token refresh
    if (response.status === 401 && !options.skipAuth) {
      try {
        const refreshed = await this.tokenManager.refreshAccessToken();
        if (refreshed && retryCount < 1) {
          return this.request<T>(method, endpoint, options.body, options, retryCount + 1);
        }
      } catch (refreshError) {
        errorMessage = 'Session expired. Please log in again.';
      }
    }
    
    // Handle server errors with retry
    if (response.status >= 500 && retryCount < (options.retries || this.maxRetries)) {
      const delay = Math.pow(2, retryCount) * 1000 + Math.random() * 1000;
      await new Promise(resolve => setTimeout(resolve, delay));
      return this.request<T>(method, endpoint, options.body, options, retryCount + 1);
    }
    
    // Show error toast (unless suppressed)
    this.handleError(
      options.customErrorMessage || errorMessage, 
      options
    );
    
    throw new Error(errorMessage);
  }
  
  private async handleNetworkError<T>(
    error: any, 
    method: string, 
    endpoint: string, 
    options: RequestOptions,
    retryCount: number
  ): Promise<T> {
    const errorMessage = error instanceof TypeError 
      ? 'Network error. Please check your connection.' 
      : error.message;
    
    // Retry for network errors
    if (error instanceof TypeError && retryCount < (options.retries || this.maxRetries)) {
      const delay = Math.pow(2, retryCount) * 1000 + Math.random() * 1000;
      await new Promise(resolve => setTimeout(resolve, delay));
      return this.request<T>(method, endpoint, options.body, options, retryCount + 1);
    }
    
    // Show error toast (unless suppressed)
    this.handleError(errorMessage, options);
    
    throw error;
  }
  
  private handleError(
    message: string, 
    options: RequestOptions
  ): void {
    // Only show toast if not suppressed
    if (!options.suppressErrorToast) {
      toastService.error(message);
    }
    
    // Optional: Log errors for debugging
    console.error('HTTP Client Error:', message);
  }
}