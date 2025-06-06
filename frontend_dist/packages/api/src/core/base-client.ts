// frontend_dist/packages/api/src/core/base-client.ts
import { TokenManager } from '@trading-app/auth';
import { getLogger } from '@trading-app/logging';
import { HttpClient, RequestOptions } from './http-client';

export abstract class BaseApiClient {  // ✅ This was correct in my original
  protected logger = getLogger(this.constructor.name);
  
  constructor(
    protected httpClient: HttpClient,
    protected tokenManager: TokenManager
  ) {}
  
  protected async get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.httpClient.get<T>(endpoint, options);
  }
  
  protected async post<T>(endpoint: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.httpClient.post<T>(endpoint, data, options);
  }
  
  protected async put<T>(endpoint: string, data?: any, options?: RequestOptions): Promise<T> {
    return this.httpClient.put<T>(endpoint, data, options);
  }
  
  protected async delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.httpClient.delete<T>(endpoint, options);
  }
  
  protected async postMultipart<T>(endpoint: string, formData: FormData, options?: RequestOptions): Promise<T> {
    return this.httpClient.postMultipart<T>(endpoint, formData, options);
  }
  
  protected checkAuthentication(): void {
    if (!this.tokenManager.isAuthenticated()) {
      throw new Error('Not authenticated');
    }
  }
}