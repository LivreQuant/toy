// src/services/auth/auth-service.ts
import { TokenManager } from './token-manager';
import { AuthApi } from '../../api/auth';
import { HttpClient } from '../../api/http-client';

interface LoginResult {
  success: boolean;
  userId?: string;
  role?: string;
  error?: string;
}

interface UserInfo {
  id: string;
  username: string;
  role: string;
}

export class AuthService {
  private tokenManager: TokenManager;
  private authApi: AuthApi;
  
  constructor(tokenManager: TokenManager) {
    this.tokenManager = tokenManager;
    const httpClient = new HttpClient('/api', tokenManager);
    this.authApi = new AuthApi(httpClient);
  }
  
  public async login(username: string, password: string): Promise<LoginResult> {
    try {
      const response = await this.authApi.login(username, password);
      
      // Store tokens
      this.tokenManager.storeTokens({
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        expiresAt: Date.now() + (response.expiresIn * 1000)
      });
      
      // Decode token to get user info
      // This is a simplified example - in a real app, you might want to validate the token
      const token = response.accessToken;
      const payload = JSON.parse(atob(token.split('.')[1]));
      
      return {
        success: true,
        userId: payload.user_id,
        role: payload.role
      };
    } catch (err) {
      console.error('Login failed:', err);
      return {
        success: false,
        error: err instanceof Error ? err.message : 'Login failed'
      };
    }
  }
  
  public async logout(): Promise<boolean> {
    try {
      await this.authApi.logout();
      this.tokenManager.clearTokens();
      return true;
    } catch (err) {
      console.error('Logout failed:', err);
      // Always clear tokens regardless of API call success
      this.tokenManager.clearTokens();
      return false;
    }
  }
  
  public async getUserInfo(): Promise<UserInfo | null> {
    try {
      // Check if we have a valid token
      const token = await this.tokenManager.getAccessToken();
      if (!token) {
        return null;
      }
      
      // Decode token to get user info
      // This is a simplified example - in a real app you might want to fetch user info from an API
      const payload = JSON.parse(atob(token.split('.')[1]));
      
      return {
        id: payload.user_id,
        username: payload.username || 'User',
        role: payload.role || 'user'
      };
    } catch (err) {
      console.error('Failed to get user info:', err);
      return null;
    }
  }
  
  public isAuthenticated(): boolean {
    return this.tokenManager.isAuthenticated();
  }
}