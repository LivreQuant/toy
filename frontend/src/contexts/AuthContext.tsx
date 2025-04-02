// src/contexts/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { TokenManager } from '../services/auth/token-manager';
import { AuthApi } from '../api/auth';
import { HttpClient } from '../api/http-client';
import { SessionStore } from '../services/session/session-manager';
import { ConnectionManager } from '../services/connection/connection-manager';
import { SessionApi } from '../api/session';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  error: string | null;
  tokenManager: TokenManager;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Create token manager first
  const tokenManager = new TokenManager();
  
  // Create HTTP client
  const httpClient = new HttpClient(tokenManager);
  
  // Create auth API client
  const authApi = new AuthApi(httpClient);
  
  // Create session API client
  const sessionApi = new SessionApi(httpClient, tokenManager);

  // Create connection manager
  const connectionManager = new ConnectionManager(tokenManager);

  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Set auth API in token manager for refresh
  useEffect(() => {
    tokenManager.setAuthApi(authApi);
  }, []);
  
  // Track recovery manager's state based on authentication
  useEffect(() => {
    connectionManager.updateRecoveryAuthState(isAuthenticated);
        
    // Disconnect if not authenticated
    if (!isAuthenticated) {
      connectionManager.disconnect();
    }
  }, [isAuthenticated]);

  // Check if user is authenticated on mount
  useEffect(() => {
    const checkAuth = async () => {
      setIsLoading(true);
      
      try {
        const isAuth = tokenManager.isAuthenticated();
        setIsAuthenticated(isAuth);
        
        if (isAuth) {
          // Verify token is still valid by fetching a token
          const token = await tokenManager.getAccessToken();
          setIsAuthenticated(!!token);
        }
      } catch (err) {
        console.error('Authentication check failed:', err);
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };
    
    checkAuth();
  }, []);
  
  // Login function
  const login = async (username: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    setError(null);
    
    try {
      // First authenticate the user
      const authResponse = await authApi.login(username, password);
      
      // Store tokens
      tokenManager.storeTokens({
        accessToken: authResponse.accessToken,
        refreshToken: authResponse.refreshToken,
        expiresAt: Date.now() + (authResponse.expiresIn * 1000),
        userId: authResponse.userId  // Store userId with the tokens
      });
      
      // Now automatically create/get a session
      const sessionResponse = await sessionApi.createSession();
      
      if (sessionResponse.success) {
        // Store session ID in local storage (not exposed to UI)
        SessionStore.setSessionId(sessionResponse.sessionId);
      }
      
      setIsAuthenticated(true);
      return true;
    } catch (err) {
      console.error('Login failed:', err);
      setError(err instanceof Error ? err.message : 'Login failed');
      setIsAuthenticated(false);
      return false;
    } finally {
      setIsLoading(false);
    }
  };
  
  // Logout function
  const logout = async (): Promise<void> => {
    setIsLoading(true);
    
    try {
      await authApi.logout();
    } catch (err) {
      console.error('Logout failed:', err);
    } finally {
      // Always clear tokens regardless of API call success
      tokenManager.clearTokens();
      
      // Also clear the session
      SessionStore.clearSession();
      
      setIsAuthenticated(false);
      setIsLoading(false);
    }
  };
  
  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        login,
        logout,
        error,
        tokenManager
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};