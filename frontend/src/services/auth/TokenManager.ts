// src/services/auth/TokenManager.ts
export interface TokenData {
    accessToken: string;
    refreshToken: string;
    expiresAt: number; // timestamp in milliseconds
  }
  
  export class TokenManager {
    private static readonly STORAGE_KEY = 'auth_tokens';
    private static readonly EXPIRY_MARGIN = 5 * 60 * 1000; // 5 minutes in milliseconds
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
          const response = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ refreshToken: tokens.refreshToken }),
          });
  
          if (!response.ok) {
            throw new Error('Failed to refresh token');
          }
  
          const data = await response.json();
          
          this.storeTokens({
            accessToken: data.accessToken,
            refreshToken: data.refreshToken || tokens.refreshToken, // Use new refresh token if provided
            expiresAt: Date.now() + (data.expiresIn * 1000),
          });
  
          // Call refresh callback if registered
          if (this.refreshCallback) {
            this.refreshCallback();
          }
  
          resolve(true);
        } catch (error) {
          console.error('Error refreshing token:', error);
          
          // If refresh fails, the user needs to re-authenticate
          this.clearTokens();
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
  
    // Parse JWT token (without validation)
    public static parseJwt(token: string): any {
      try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(
          atob(base64)
            .split('')
            .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
            .join('')
        );
        return JSON.parse(jsonPayload);
      } catch (e) {
        console.error('Failed to parse JWT token', e);
        return null;
      }
    }
  }