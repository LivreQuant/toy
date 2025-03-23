// src/services/api/AuthService.ts
import { TokenData } from '../auth/TokenManager';

export class AuthService {
  private static readonly API_URL = '/api/auth';
  
  public static async login(username: string, password: string): Promise<TokenData> {
    const response = await fetch(`${this.API_URL}/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
      credentials: 'include', // Important for cookies
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Login failed');
    }
    
    const data = await response.json();
    
    // Return token data
    return {
      accessToken: data.accessToken,
      refreshToken: '', // The refresh token is stored in HTTP-only cookie
      expiresAt: Date.now() + (data.expiresIn * 1000),
    };
  }
  
  public static async refreshToken(): Promise<TokenData> {
    const response = await fetch(`${this.API_URL}/refresh`, {
      method: 'POST',
      credentials: 'include', // Important for cookies
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Token refresh failed');
    }
    
    const data = await response.json();
    
    // Return token data
    return {
      accessToken: data.accessToken,
      refreshToken: '', // The refresh token is stored in HTTP-only cookie
      expiresAt: Date.now() + (data.expiresIn * 1000),
    };
  }
  
  public static async logout(): Promise<void> {
    await fetch(`${this.API_URL}/logout`, {
      method: 'POST',
      credentials: 'include', // Important for cookies
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('accessToken') || ''}`,
      },
    });
    
    // Remove tokens from local storage
    localStorage.removeItem('accessToken');
    localStorage.removeItem('tokenExpiry');
  }
}