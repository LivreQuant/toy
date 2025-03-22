// src/services/api/HttpClient.ts
import { TokenManager } from '../auth/TokenManager';

export class HttpClient {
  private readonly baseUrl: string;
  private readonly tokenManager: TokenManager;
  
  constructor(baseUrl: string, tokenManager: TokenManager) {
    this.baseUrl = baseUrl;
    this.tokenManager = tokenManager;
  }
  
  public async get<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    return this.request<T>('GET', endpoint, undefined, options);
  }
  
  public async post<T>(endpoint: string, data?: any, options: RequestInit = {}): Promise<T> {
    return this.request<T>('POST', endpoint, data, options);
  }
  
  public async put<T>(endpoint: string, data?: any, options: RequestInit = {}): Promise<T> {
    return this.request<T>('PUT', endpoint, data, options);
  }
  
  public async delete<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    return this.request<T>('DELETE', endpoint, undefined, options);
  }
  
  private async request<T>(
    method: string, 
    endpoint: string, 
    data?: any, 
    customOptions: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    // Get the current access token
    const accessToken = await this.tokenManager.getAccessToken();
    
    // Setup request headers
    const headers = new Headers(customOptions.headers);
    
    if (accessToken) {
      headers.set('Authorization', `Bearer ${accessToken}`);
    }
    
    if (data && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    
    // Build request options
    const options: RequestInit = {
      ...customOptions,
      method,
      headers,
      credentials: 'include', // Important for cookies
      body: data ? JSON.stringify(data) : undefined,
    };
    
    // Make the request
    const response = await fetch(url, options);
    
    // Handle 401 Unauthorized - Token might be expired
    if (response.status === 401) {
      // Try to refresh the token
      const refreshed = await this.tokenManager.refreshAccessToken();
      
      if (refreshed) {
        // Retry the request with new token
        const newAccessToken = await this.tokenManager.getAccessToken();
        headers.set('Authorization', `Bearer ${newAccessToken}`);
        
        const retryOptions = {
          ...options,
          headers,
        };
        
        const retryResponse = await fetch(url, retryOptions);
        
        if (retryResponse.ok) {
          return await retryResponse.json();
        }
      }
      
      // If refresh failed or retry failed, throw error
      throw new Error('Unauthorized - Please log in again');
    }
    
    // Handle other error responses
    if (!response.ok) {
      let errorMessage = 'Request failed';
      try {
        const errorData = await response.json();
        errorMessage = errorData.error || errorData.message || errorMessage;
      } catch (e) {
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
  }
}