// src/services/auth/token-manager.ts
import { AuthApi } from '../../api/auth';

export interface TokenData {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // timestamp in milliseconds
}

export class TokenManager {
  private static readonly STORAGE_KEY = 'auth_tokens';
  private static readonly EXPIRY_MARGIN = 5 * 60 * 1000; // 5 minutes in milliseconds
  private authApi?: AuthApi;
  private refreshPromise: Promise<boolean> | null = null;
  private refreshCallback: (() => void) | null = null;

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

  // Refresh the access token using refresh token
  public async refreshAccessToken(): Promise<boolean> {
    // If already refreshing, return the existing promise
    if (this.refreshPromise) {
      return this.refreshPromise;
    }
  
    const tokens = this.getTokens();
    if (!tokens?.refreshToken) {
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
        });
  
        // Rest of your code...
        
        resolve(true);
      } catch (error) {
        // Error handling...
        resolve(false);
      } finally {
        this.refreshPromise = null;
      }
    });
  
    return this.refreshPromise;
  }
  
  // Register a callback to be called when tokens are refreshed
  public onTokenRefresh(callback: () => void): void {
    this.refreshCallback = callback;
  }
}