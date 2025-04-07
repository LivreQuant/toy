import React, { createContext, useState, useEffect, useCallback, ReactNode, useMemo } from 'react';
import { LoginRequest, LoginResponse, AuthApi } from '../api/auth';
import { TokenManager, TokenData } from '../services/auth/token-manager';
import LoadingSpinner from '../components/Common/LoadingSpinner'; // Assuming component exists

interface AuthContextProps {
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  userId: string | number | null;
  login: (credentials: LoginRequest) => Promise<boolean>;
  logout: () => Promise<void>;
  tokenManager: TokenManager; // Expose for direct use if needed (e.g., in HttpClient)
}

export const AuthContext = createContext<AuthContextProps | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
  tokenManager: TokenManager; // Receive instances via props
  authApi: AuthApi;         // Receive instances via props
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children, tokenManager, authApi }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isAuthLoading, setIsAuthLoading] = useState<boolean>(true); // Start loading
  const [userId, setUserId] = useState<string | number | null>(null);

  // Check authentication status on mount
  useEffect(() => {
    const checkAuth = () => {
      const authenticated = tokenManager.isAuthenticated();
      console.log("*** AUTH: Initial auth check: authenticated=", authenticated);
      setIsAuthenticated(authenticated);
      setUserId(authenticated ? tokenManager.getUserId() : null);
      setIsAuthLoading(false); // Finished loading
    };
    checkAuth();
  
    // Listen for token refresh events to update auth state
    const handleRefresh = (success: boolean) => {
      console.log("*** AUTH: Token refresh event: success=", success);
      setIsAuthenticated(success && tokenManager.isAuthenticated());
      setUserId(success && tokenManager.isAuthenticated() ? tokenManager.getUserId() : null);
    };
    tokenManager.addRefreshListener(handleRefresh);
  
    return () => {
      tokenManager.removeRefreshListener(handleRefresh);
    };
  }, [tokenManager]);

  // In AuthProvider.tsx - add in login function:
  const login = useCallback(async (credentials: LoginRequest): Promise<boolean> => {
    setIsAuthLoading(true);
    try {
      const response: LoginResponse = await authApi.login(credentials.username, credentials.password);
      const tokenData: TokenData = {
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        expiresAt: Date.now() + response.expiresIn * 1000,
        userId: response.userId,
      };
      tokenManager.storeTokens(tokenData);
      setIsAuthenticated(true);
      setUserId(response.userId);
      setIsAuthLoading(false);
      return true;
    } catch (error: any) {
      console.error("Login failed:", error);
      tokenManager.clearTokens(); // Ensure tokens are cleared on failed login
      setIsAuthenticated(false);
      setUserId(null);
      setIsAuthLoading(false);
      // Error handling (e.g., toast notification) is likely handled by HttpClient/ErrorHandler
      return false;
    }
  }, [authApi, tokenManager]);

  const logout = useCallback(async (): Promise<void> => {
    setIsAuthLoading(true); // Optional: Show loading during logout
    try {
        // Optional: Call backend logout endpoint
        // It's crucial to clear local tokens regardless of backend call success
        await authApi.logout();
    } catch (error) {
        console.error("Backend logout failed, clearing local session anyway:", error);
         // Error handling is likely handled by HttpClient/ErrorHandler
    } finally {
        tokenManager.clearTokens();
        setIsAuthenticated(false);
        setUserId(null);
        setIsAuthLoading(false);
         // Optionally disconnect connection manager here
         // connectionManager?.disconnect('user_logout');
    }
  }, [authApi, tokenManager]);

  const contextValue = useMemo(() => ({
    isAuthenticated,
    isAuthLoading,
    userId,
    login,
    logout,
    tokenManager // Provide the instance
  }), [isAuthenticated, isAuthLoading, userId, login, logout, tokenManager]);

  // Render a loading screen while checking auth status initially
  if (isAuthLoading && !isAuthenticated) {
     // Avoid flash of loading if already authenticated and just re-checking
    return <LoadingSpinner message="Initializing session..." />;
  }

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};