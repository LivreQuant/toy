// src/api/http-client.ts
import { TokenManager } from '../services/auth/token-manager';
import { config } from '../config';
import { getLogger } from '../boot/logging';

export interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
  retries?: number; // Used internally for retrying after token refresh or server error
  suppressErrorToast?: boolean; // Flag to suppress automatic error toasts
  customErrorMessage?: string; // Custom message for error handling
  context?: string; // Optional context string for logging/error reporting
}

export class HttpClient {
  private readonly baseUrl: string;
  private readonly tokenManager: TokenManager;
  private readonly maxRetries: number = 2; // Max retries for 5xx errors
  private readonly logger = getLogger('HttpClient');

  constructor(tokenManager: TokenManager) {
    this.baseUrl = config.apiBaseUrl;
    this.tokenManager = tokenManager;
  }

  // Public methods (no changes needed here, they call the private request method)
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

  // FIX: Define expected parameters based on internal calls
  private async request<T>(
    method: string,
    endpoint: string,
    data?: any,
    options: RequestOptions = {},
    retryCount: number = 0 // Internal counter for retries
  ): Promise<T> {
      /* --- FULL IMPLEMENTATION IS MISSING --- */
      // This is a placeholder structure based on the error handling logic below.
      // The actual fetch call, header setup, body stringification, etc., needs to be here.
      // It must handle the promise returned by fetch and either resolve with T or throw.

      const url = `${this.baseUrl}${endpoint}`;
      const headers = new Headers(options.headers || {});
      headers.append('Content-Type', 'application/json');
      // Add Authorization header if needed
      if (!options.skipAuth) {
          const token = await this.tokenManager.getAccessToken(); // Handles refresh internally
          if (!token) {
              throw new Error("Not authenticated"); // Or handle redirect
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
          const response = await fetch(url, fetchOptions);

          if (!response.ok) {
              // Delegate HTTP status code errors to the handler
              return await this.handleHttpErrorResponse<T>(response, method, endpoint, data, options, retryCount);
          }

          // Handle successful responses
          if (response.status === 204) { // No Content
             // Type assertion needed as response body is empty
              return undefined as unknown as T;
          }

          // Assuming successful responses return JSON
          const responseData = await response.json();
          return responseData as T;

      } catch (networkError: any) {
          // Delegate network errors (fetch failure) to the other handler
          return await this.handleNetworkOrFetchError<T>(networkError, method, endpoint, data, options, retryCount);
      }

      // --- END OF MISSING IMPLEMENTATION PLACEHOLDER ---
  }


  private async handleHttpErrorResponse<T>(
    response: Response,
    method: string,
    endpoint: string,
    data: any, // Include data for potential retries
    options: RequestOptions,
    retryCount: number
  ): Promise<T> {
    let errorMessage = options.customErrorMessage || `HTTP Error ${response.status}: ${response.statusText}`;
    let errorDetails: any = null;
    try {
        // Attempt to parse error details from the response body
        errorDetails = await response.json();
        // Use detailed message from API if available
        if (typeof errorDetails?.message === 'string') {
          errorMessage = errorDetails.message;
        } else if (typeof errorDetails?.error === 'string') {
           errorMessage = errorDetails.error;
        }
    } catch (e) {
        // Ignore if body isn't valid JSON or empty
        this.logger.debug('Could not parse error response body as JSON', { status: response.status, endpoint });
    }

    // --- Specific Status Code Handling ---
    if (response.status === 401 && !options.skipAuth && retryCount < 1) { // Only retry 401 once
       this.logger.warn('Received 401 Unauthorized, attempting token refresh...', { endpoint });
      try {
        const refreshed = await this.tokenManager.refreshAccessToken();
        if (refreshed) {
           this.logger.info('Token refresh successful, retrying original request.', { endpoint });
           // FIX: Pass 5 arguments to request
           return this.request<T>(method, endpoint, data, options, retryCount + 1);
        } else {
            this.logger.error('Token refresh failed after 401.', { endpoint });
            errorMessage = options.customErrorMessage || 'Session expired or invalid. Please log in again.';
            this.logger.error(`[TokenManager.RefreshFailed] ${errorMessage}`);
            throw new Error(errorMessage); // Throw after handling
        }
      } catch (refreshError: any) {
        this.logger.error('Error during token refresh attempt', { endpoint, error: refreshError.message });
        errorMessage = options.customErrorMessage || 'Session refresh failed. Please log in again.';
        this.logger.error(`[TokenManager.RefreshException] ${errorMessage}`);
        throw new Error(errorMessage); // Throw after handling
      }
    } else if (response.status === 403) { // Forbidden
        errorMessage = options.customErrorMessage || errorDetails?.message || 'Permission denied.';
        this.logger.error(`[Forbidden] ${errorMessage}`);
    } else if (response.status === 404) { // Not Found
        errorMessage = options.customErrorMessage || errorDetails?.message || 'Resource not found.';
        this.logger.error(`[NotFound] ${errorMessage}`);
        // Use generic handler, maybe suppress toast?
    } else if (response.status >= 400 && response.status < 500) { // Other Client Errors (e.g., 400 Bad Request, 409 Conflict)
        errorMessage = options.customErrorMessage || errorDetails?.message || `Client error ${response.status}.`;
        this.logger.error(`.ClientError${response.status} ${errorMessage}`);
    } else if (response.status >= 500) { // Server Errors (500, 502, 503, 504)
        errorMessage = options.customErrorMessage || `Server error (${response.status}). Please try again later.`;
         // Retry mechanism for server errors (simple example)
         const maxRetriesForServerError = options.retries ?? this.maxRetries; // Use option or default
         if (retryCount < maxRetriesForServerError) {
            const delay = Math.pow(2, retryCount) * 500 + (Math.random() * 500); // Exponential backoff + jitter
            this.logger.warn(`Server error ${response.status}. Retrying request in ${delay.toFixed(0)}ms (attempt ${retryCount + 1}/${maxRetriesForServerError})`, { endpoint });
            await new Promise(resolve => setTimeout(resolve, delay));
             // FIX: Pass 5 arguments to request
            return this.request<T>(method, endpoint, data, options, retryCount + 1);
         } else {
             this.logger.error(`Server error ${response.status} persisted after ${maxRetriesForServerError} retries.`, { endpoint, details: errorDetails });
             this.logger.error(`.ServerError${response.status} ${errorMessage}`);
         }
    }

    // --- Default Error Handling for unhandled status codes ---
    if (response.status >= 400) { // Ensure only errors are thrown
        // Use generic error for anything not specifically handled above
        this.logger.error(`.Unhandled${response.status} ${errorMessage}`);
        throw new Error(errorMessage);
    }

    // Should not be reached if response.ok was false, but satisfy TS path checks
    this.logger.error("handleHttpErrorResponse reached unexpectedly for non-error response", { status: response.status });
    throw new Error("Unexpected non-error response in error handler");
  }

  // FIX: Add expected parameters and return type
   private async handleNetworkOrFetchError<T>(
        error: Error,
        method: string,
        endpoint: string,
        data: any,
        options: RequestOptions,
        retryCount: number
    ): Promise<T> {
        /* --- FULL IMPLEMENTATION IS MISSING --- */
        // This should contain logic for handling fetch exceptions (e.g., network down, DNS error).
        // It might include retries similar to the 5xx handling.
        const errorMessage = options.customErrorMessage || `Network error: ${error.message}`;
        const errorContext = options.context || `HttpClient.${method}.${endpoint.replace('/', '')}`;

        this.logger.error('Network or fetch error occurred', { endpoint, error: error.message, retryCount });

        // Example: Simple retry logic (adjust as needed)
        const maxRetriesForNetworkError = options.retries ?? this.maxRetries;
        if (retryCount < maxRetriesForNetworkError) {
            const delay = Math.pow(2, retryCount) * 1000 + (Math.random() * 1000); // Exponential backoff + jitter
            this.logger.warn(`Network error. Retrying request in ${delay.toFixed(0)}ms (attempt ${retryCount + 1}/${maxRetriesForNetworkError})`, { endpoint });
            await new Promise(resolve => setTimeout(resolve, delay));
            // FIX: Pass 5 arguments to request
            return this.request<T>(method, endpoint, data, options, retryCount + 1);
        } else {
            this.logger.error(`Network error persisted after ${maxRetriesForNetworkError} retries.`, { endpoint });
            this.logger.error(`.NetworkError.Final ${errorMessage}`);
            throw new Error(errorMessage); // Throw final error
        }
   }
}