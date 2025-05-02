// src/api/http-client.ts
import { TokenManager } from '../services/auth/token-manager';
import { DeviceIdManager } from '../services/auth/device-id-manager'; 
import { config } from '../config';
import { getLogger } from '../boot/logging';
import { toastService } from '../services/notification/toast-service';

export interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
  retries?: number; 
  suppressErrorToast?: boolean; 
  customErrorMessage?: string; 
  context?: string; 
}

export class HttpClient {
  private readonly logger = getLogger('HttpClient');

  private readonly baseUrl: string;
  private readonly tokenManager: TokenManager;
  private readonly maxRetries: number = 0; // NO RETRIES

  constructor(tokenManager: TokenManager) {
    this.baseUrl = config.apiBaseUrl;
    this.tokenManager = tokenManager;
  }

  // Public methods
  public async get<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    return this.request<T>('GET', endpoint, undefined, options);
  }
  
  public async post<T>(endpoint: string, data?: any, options: RequestOptions = {}): Promise<T> {
    // For orders, always set retries to 0
    if (endpoint.includes('/orders/submit') || endpoint.includes('/orders/cancel')) {
      options.retries = 0; // Force zero retries for orders
    }
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
    retryCount: number = 0 
  ): Promise<T> {
    // Never retry order operations
    if ((endpoint.includes('/orders/submit') || endpoint.includes('/orders/cancel')) && retryCount > 0) {
      this.logger.error(`BLOCKING RETRY attempt for order endpoint: ${endpoint}`, { retryCount });
      throw new Error("Order operations cannot be retried");
    }

    // Create full URL string
    const fullUrl = `${this.baseUrl}${endpoint}`;
    
    // Get device ID for authentication
    const deviceId = DeviceIdManager.getInstance().getDeviceId();
    
    // Add deviceId as a query parameter by appending to endpoint string
    const urlWithDeviceId = fullUrl + (fullUrl.includes('?') ? '&' : '?') + `deviceId=${deviceId}`;
   
    const headers = new Headers(options.headers || {});
    headers.append('Content-Type', 'application/json');

    // Add Authorization header if needed
    if (!options.skipAuth) {
      const token = await this.tokenManager.getAccessToken(); // Handles refresh internally
      if (!token) {
        throw new Error("Not authenticated"); 
      }
      headers.append('Authorization', `Bearer ${token}`);
    }

    const fetchOptions: RequestInit = {
      ...options,
      method: method,
      headers: headers,
      body: data ? JSON.stringify(data) : undefined,
    };

    try {
      const response = await fetch(urlWithDeviceId, fetchOptions);

      if (!response.ok) {
        return await this.handleHttpErrorResponse<T>(response, method, endpoint, data, options, retryCount);
      }

      // Handle successful responses
      if (response.status === 204) { // No Content
        return undefined as unknown as T;
      }

      // Assuming successful responses return JSON
      const responseData = await response.json();
      return responseData as T;

    } catch (networkError: any) {
      // Handle network failures (never retry orders)
      if (endpoint.includes('/orders/submit') || endpoint.includes('/orders/cancel')) {
        this.logger.error(`Network error for order endpoint: ${endpoint} - NO RETRY`, { 
          error: networkError.message 
        });
        throw new Error(`Network error for order operation: ${networkError.message} - NOT RETRIED`);
      }
      
      return await this.handleNetworkOrFetchError<T>(networkError, method, endpoint, data, options, retryCount);
    }
  }

  private async handleHttpErrorResponse<T>(
    response: Response,
    method: string,
    endpoint: string,
    data: any,
    options: RequestOptions,
    retryCount: number
  ): Promise<T> {
    let errorMessage = options.customErrorMessage || `HTTP Error ${response.status}: ${response.statusText}`;
    let errorDetails: any = null;
    try {
      errorDetails = await response.json();
      if (typeof errorDetails?.message === 'string') {
        errorMessage = errorDetails.message;
      } else if (typeof errorDetails?.error === 'string') {
         errorMessage = errorDetails.error;
      }
    } catch (e) {
      this.logger.debug('Could not parse error response body as JSON', { status: response.status, endpoint });
    }

    // Check if this is an order endpoint - never retry
    if (endpoint.includes('/orders/submit') || endpoint.includes('/orders/cancel')) {
      this.logger.error(`Error for order endpoint ${endpoint}: ${response.status} - NO RETRY`, { 
        status: response.status, 
        error: errorMessage
      });
      
      // Show error toast for order operations unless suppressed
      if (!options.suppressErrorToast) {
        toastService.error(`Order operation failed: ${errorMessage}`);
      }
      
      throw new Error(`Order operation failed (${response.status}): ${errorMessage} - NOT RETRIED`);
    }

    // --- Handle different status codes ---
    if (response.status === 401 && !options.skipAuth && retryCount < 1) {
      this.logger.warn('Received 401 Unauthorized, attempting token refresh...', { endpoint });
      try {
        const refreshed = await this.tokenManager.refreshAccessToken();
        if (refreshed) {
          this.logger.info('Token refresh successful, retrying original request.', { endpoint });
          return this.request<T>(method, endpoint, data, options, retryCount + 1);
        } else {
          errorMessage = options.customErrorMessage || 'Session expired or invalid. Please log in again.';
          this.logger.error(`Token refresh failed after 401. ${errorMessage}`);
          
          // Show session expired toast unless suppressed
          if (!options.suppressErrorToast) {
            toastService.error(errorMessage, 0); // Manual dismiss for important auth errors
          }
          
          throw new Error(errorMessage);
        }
      } catch (refreshError: any) {
        errorMessage = options.customErrorMessage || 'Session refresh failed. Please log in again.';
        this.logger.error(`Error during token refresh attempt. ${errorMessage}`);
        
        // Show session refresh error toast unless suppressed
        if (!options.suppressErrorToast) {
          toastService.error(errorMessage, 0);
        }
        
        throw new Error(errorMessage);
      }
    } else if (response.status === 403) {
      errorMessage = options.customErrorMessage || errorDetails?.message || 'Permission denied.';
      this.logger.error(`[Forbidden] ${errorMessage}`);
      
      // Show permission error toast unless suppressed
      if (!options.suppressErrorToast) {
        toastService.error(`Access denied: ${errorMessage}`);
      }
    } else if (response.status === 404) {
      errorMessage = options.customErrorMessage || errorDetails?.message || 'Resource not found.';
      this.logger.error(`[NotFound] ${errorMessage}`);
      
      // Show not found toast unless suppressed
      if (!options.suppressErrorToast) {
        toastService.warning(`Not found: ${errorMessage}`);
      }
    } else if (response.status >= 400 && response.status < 500) {
      errorMessage = options.customErrorMessage || errorDetails?.message || `Client error ${response.status}.`;
      this.logger.error(`.ClientError${response.status} ${errorMessage}`);
      
      // Show client error toast unless suppressed
      if (!options.suppressErrorToast) {
        toastService.error(errorMessage);
      }
    } else if (response.status >= 500) {
      errorMessage = options.customErrorMessage || `Server error (${response.status}). NOT RETRYING.`;
      
      // Never retry 5xx errors for order endpoints
      if (!endpoint.includes('/orders/submit') && !endpoint.includes('/orders/cancel')) {
        const maxRetriesForServerError = options.retries ?? this.maxRetries;
        if (retryCount < maxRetriesForServerError) {
          const delay = Math.pow(2, retryCount) * 500 + (Math.random() * 500);
          this.logger.warn(`Server error ${response.status}. Retrying request in ${delay.toFixed(0)}ms (attempt ${retryCount + 1}/${maxRetriesForServerError})`, { endpoint });
          
          // Show retry toast unless suppressed
          if (!options.suppressErrorToast) {
            toastService.info(`Server error. Retrying in ${Math.round(delay/1000)} seconds...`);
          }
          
          await new Promise(resolve => setTimeout(resolve, delay));
          return this.request<T>(method, endpoint, data, options, retryCount + 1);
        } else {
          this.logger.error(`Server error ${response.status} persisted after ${maxRetriesForServerError} retries.`, { endpoint, details: errorDetails });
          
          // Show persistent server error toast unless suppressed
          if (!options.suppressErrorToast) {
            toastService.error(`Server error persisted after multiple retries: ${errorMessage}`, 0);
          }
        }
      } else {
        this.logger.error(`Server error ${response.status} for order endpoint: ${endpoint} - NO RETRY ATTEMPTED`, { endpoint });
        
        // Show server error toast for order endpoints unless suppressed
        if (!options.suppressErrorToast) {
          toastService.error(`Server error for order operation: ${errorMessage}`);
        }
      }
    }

    if (response.status >= 400) {
      this.logger.error(`.Unhandled${response.status} ${errorMessage}`);
      
      // Show general error toast unless suppressed
      if (!options.suppressErrorToast) {
        toastService.error(errorMessage);
      }
      
      throw new Error(errorMessage);
    }

    this.logger.error("handleHttpErrorResponse reached unexpectedly for non-error response", { status: response.status });
    throw new Error("Unexpected non-error response in error handler");
  }

  private async handleNetworkOrFetchError<T>(
      error: Error,
      method: string,
      endpoint: string,
      data: any,
      options: RequestOptions,
      retryCount: number
  ): Promise<T> {
      const errorMessage = options.customErrorMessage || `Network error: ${error.message}`;

      this.logger.error('Network or fetch error occurred', { endpoint, error: error.message, retryCount });

      // Never retry order operations
      if (endpoint.includes('/orders/submit') || endpoint.includes('/orders/cancel')) {
        this.logger.error(`Network error for order endpoint: ${endpoint} - NO RETRY`, { 
          error: error.message 
        });
        
        // Show network error toast for order operations unless suppressed
        if (!options.suppressErrorToast) {
          toastService.error(`Network error for order operation: ${error.message}`);
        }
        
        throw new Error(`Network error for order operation: ${error.message} - NOT RETRIED`);
      }
      
      // Simple retry logic for non-order operations
      const maxRetriesForNetworkError = options.retries ?? this.maxRetries;
      if (retryCount < maxRetriesForNetworkError) {
          const delay = Math.pow(2, retryCount) * 1000 + (Math.random() * 1000);
          this.logger.warn(`Network error. Retrying request in ${delay.toFixed(0)}ms (attempt ${retryCount + 1}/${maxRetriesForNetworkError})`, { endpoint });
          
          // Show retry toast unless suppressed
          if (!options.suppressErrorToast) {
            toastService.info(`Connection issue. Retrying in ${Math.round(delay/1000)} seconds...`);
          }
          
          await new Promise(resolve => setTimeout(resolve, delay));
          return this.request<T>(method, endpoint, data, options, retryCount + 1);
      } else {
          this.logger.error(`Network error persisted after. ${errorMessage}`);
          
          // Show persistent network error toast unless suppressed
          if (!options.suppressErrorToast) {
            toastService.error(`Connection failed: ${errorMessage}`, 0); // Manual dismiss for persistent errors
          }
          
          throw new Error(errorMessage);
      }
  }
}