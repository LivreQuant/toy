// src/services/auth/token-manager.ts
import { AuthApi } from '../../api/auth';
import { DeviceIdManager } from '../../utils/device-id-manager';
import { ErrorHandler, ErrorSeverity } from '../../utils/error-handler';

export interface TokenData {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // timestamp in milliseconds
  userId: string | number; // Add userId to the token data
}

// src/services/auth/token-manager.ts
export class TokenManager {
  private static readonly STORAGE_KEY = 'auth_tokens';
  private static readonly EXPIRY_MARGIN = 5 * 60 * 1000; // 5 minutes in milliseconds
  private authApi?: AuthApi;
  private refreshPromise: Promise<boolean> | null = null;
  private refreshListeners: Set<Function> = new Set();

  // Store tokens in local storage
  public storeTokens(tokenData: TokenData): void {
    localStorage.setItem(TokenManager.STORAGE_KEY, JSON.stringify(tokenData));
  }

  // Get stored tokens
  public getTokens(): TokenData | null {
    const tokenStr = localStorage.getItem(TokenManager.STORAGE_KEY);
    if (!tokenStr) return null;

    try {
      return JSON.parse(tokenStr) as TokenData;
    } catch (e) {
      console.error('Failed to parse stored tokens', e);
      this.clearTokens(); // Clear invalid tokens
      return null;
    }
  }

  // Clear tokens (on logout)
  public clearTokens(): void {
    localStorage.removeItem(TokenManager.STORAGE_KEY);
  }

  // Check if tokens are present and valid
  public isAuthenticated(): boolean {
    const tokens = this.getTokens();
    return tokens !== null && tokens.expiresAt > Date.now();
  }

  // Set the API instance (called after token manager is created)
  public setAuthApi(authApi: AuthApi): void {
    this.authApi = authApi;
  }

  // Add listener for token refresh events
  public addRefreshListener(listener: Function): void {
    this.refreshListeners.add(listener);
  }

  // Remove listener
  public removeRefreshListener(listener: Function): void {
    this.refreshListeners.delete(listener);
  }

  // Get access token (automatically refreshing if needed)
  public async getAccessToken(): Promise<string | null> {
    const tokens = this.getTokens();
    if (!tokens) return null;

    // If token expires soon, refresh it
    if (tokens.expiresAt - Date.now() < TokenManager.EXPIRY_MARGIN) {
      const success = await this.refreshAccessToken();
      if (!success) return null;
      
      // Get updated tokens
      const updatedTokens = this.getTokens();
      return updatedTokens?.accessToken || null;
    }

    return tokens.accessToken;
  }

  public getUserId(): string | number | null {
    const tokens = this.getTokens();
    return tokens?.userId || null;
  }
  
  // Refresh the access token using refresh token
  public async refreshAccessToken(): Promise<boolean> {
    // If already refreshing, return the existing promise
    if (this.refreshPromise) {
      return this.refreshPromise;
    }
  
    const tokens = this.getTokens();
    if (!tokens?.refreshToken) {
      console.error('No refresh token available');
      return false;
    }
  
    this.refreshPromise = new Promise<boolean>(async (resolve) => {
      try {
        // Add null check for authApi
        if (!this.authApi) {
          console.error('Auth API not initialized');
          resolve(false);
          return;
        }
  
        const response = await this.authApi.refreshToken(tokens.refreshToken);
        
        this.storeTokens({
          accessToken: response.accessToken,
          refreshToken: response.refreshToken,
          expiresAt: Date.now() + (response.expiresIn * 1000),
          userId: response.userId  // Store userId with the tokens
        });
  
        // Notify listeners about the token refresh
        this.notifyRefreshListeners(true);
        
        resolve(true);
      } catch (error) {
        console.error('Token refresh failed:', error);
        
        // Notify listeners about the failed refresh
        this.notifyRefreshListeners(false);
        
        resolve(false);
      } finally {
        this.refreshPromise = null;
      }
    });
  
    return this.refreshPromise;
  }

  // Notify all registered listeners
  private notifyRefreshListeners(success: boolean): void {
    for (const listener of this.refreshListeners) {
      try {
        listener(success);
      } catch (error) {
        console.error('Error in token refresh listener:', error);
      }
    }
  }
}