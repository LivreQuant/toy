// src/hooks/useAuth.ts
import { useEffect, useState, useCallback } from 'react';
import { TokenManager } from '../services/auth/token-manager';
import { AuthApi } from '../api/auth';

export function useAuth(tokenManager: TokenManager, authApi: AuthApi) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => tokenManager.isAuthenticated());
  
  // Update auth state when tokens change
  const checkAuthStatus = useCallback(() => {
    setIsAuthenticated(tokenManager.isAuthenticated());
  }, [tokenManager]);
  
  // Login function
  const login = useCallback(async (credentials: { username: string, password: string }) => {
    try {
      const response = await authApi.login(credentials);
      
      tokenManager.storeTokens({
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        expiresAt: Date.now() + (response.expiresIn * 1000),
        userId: response.userId
      });
      
      setIsAuthenticated(true);
      return { success: true };
    } catch (error) {
      console.error('Login failed:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Login failed' 
      };
    }
  }, [authApi, tokenManager]);
  
  // Logout function
  const logout = useCallback(() => {
    tokenManager.clearTokens();
    setIsAuthenticated(false);
  }, [tokenManager]);
  
  // Setup listener for auth state changes
  useEffect(() => {
    // Add storage event listener to handle logout in other tabs
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === 'auth_tokens' || event.key === null) {
        checkAuthStatus();
      }
    };
    
    window.addEventListener('storage', handleStorageChange);
    
    // Add refresh listener
    const refreshListener = (success: boolean) => {
      checkAuthStatus();
    };
    
    tokenManager.addRefreshListener(refreshListener);
    
    // Clean up
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      tokenManager.removeRefreshListener(refreshListener);
    };
  }, [tokenManager, checkAuthStatus]);
  
  return {
    isAuthenticated,
    login,
    logout,
    getUserId: () => tokenManager.getUserId(),
    refreshToken: () => tokenManager.refreshAccessToken()
  };
}