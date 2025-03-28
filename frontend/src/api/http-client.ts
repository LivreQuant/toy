// src/api/http-client.ts
import { TokenManager } from '../services/auth/token-manager';
import { config } from '../config';

export interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
  retries?: number;
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
      const token = await this.tokenManager.getAccessToken();
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
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
      credentials: 'include', // For cookies if needed
    };
    
    try {
      const response = await fetch(url, requestOptions);
      
      // Log full response for debugging
      console.log('Full response:', {
        status: response.status,
        statusText: response.statusText,
        headers: Object.fromEntries(response.headers.entries())
      });
      
      if (!response.ok) {
        // More detailed error handling
        const errorText = await response.text();
        console.error('Error response:', errorText);
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
      }
      
      // Handle 401 Unauthorized - Token might be expired
      if (response.status === 401 && !options.skipAuth && retryCount < 1) {
        // Try to refresh the token
        const refreshed = await this.tokenManager.refreshAccessToken();
        
        if (refreshed) {
          // Retry the request with new token
          return this.request<T>(method, endpoint, data, options, retryCount + 1);
        }
        
        // If refresh failed, throw error
        throw new Error('Unauthorized - Please log in again');
      }
      
      // Handle server errors with retry
      if (response.status >= 500 && retryCount < (options.retries || this.maxRetries)) {
        // Exponential backoff
        const delay = Math.pow(2, retryCount) * 1000 + Math.random() * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
        return this.request<T>(method, endpoint, data, options, retryCount + 1);
      }
      
      // Handle other error responses
      if (!response.ok) {
        let errorMessage = 'Request failed';
        try {
          const errorData = await response.json();
          errorMessage = errorData.error || errorData.message || errorMessage;
        } catch {
          // If response is not JSON, use status text
          errorMessage = response.statusText;
        }
        throw new Error(errorMessage);
      }
      
      // Parse response if it has content
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }
      
      return {} as T;
    } catch (error) {
      // Network errors or JSON parsing errors
      if (error instanceof TypeError && error.message.includes('Failed to fetch') && 
          retryCount < (options.retries || this.maxRetries)) {
        // Exponential backoff for network errors
        const delay = Math.pow(2, retryCount) * 1000 + Math.random() * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
        return this.request<T>(method, endpoint, data, options, retryCount + 1);
      }
      
      throw error;
    }
  }
}