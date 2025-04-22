// Likely inside src/contexts/AuthContext.tsx

import React, { createContext, useState, useEffect, useCallback, ReactNode, useMemo } from 'react';
import { LoginRequest, LoginResponse, AuthApi } from '../api/auth'; // Adjust path as needed
import { TokenManager, TokenData } from '../services/auth/token-manager'; // Adjust path
import LoadingSpinner from '../components/Common/LoadingSpinner'; // Assuming component exists
// --->>> ADD THIS IMPORT <<<---
import { appState } from '../state/app-state.service'; // Adjust path as needed
import { getLogger } from '../boot/logging'; // Adjust path as needed
import { DeviceIdManager } from '../services/auth/device-id-manager';
import { ConnectionManager } from '../services/connection/connection-manager';

const logger = getLogger('AuthContext'); // Initialize logger for this context

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
  connectionManager: ConnectionManager;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children, tokenManager, authApi, connectionManager }) => {
  // Use initial state from token manager for consistency on load
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => tokenManager.isAuthenticated());
  const [isAuthLoading, setIsAuthLoading] = useState<boolean>(true); // Start loading
  const [userId, setUserId] = useState<string | number | null>(() => tokenManager.getUserId());

  // Check authentication status on mount and sync global state
  useEffect(() => {
    const checkAuth = () => {
      const authenticated = tokenManager.isAuthenticated();
      const currentUserId = authenticated ? tokenManager.getUserId() : null;
      logger.info(`Initial auth check: authenticated=${authenticated}, userId=${currentUserId}`);
      setIsAuthenticated(authenticated);
      setUserId(currentUserId);
      // Sync global state on initial load as well
      appState.updateAuthState({
          isAuthenticated: authenticated,
          isAuthLoading: false, // Finished loading
          userId: currentUserId,
          lastAuthError: null // Clear any previous error on load
      });
      setIsAuthLoading(false); // Finished local loading state
    };
    checkAuth();

    // Listen for token refresh events to update auth state
    const handleRefresh = (success: boolean) => {
      const refreshedIsAuth = success && tokenManager.isAuthenticated();
      const refreshedUserId = refreshedIsAuth ? tokenManager.getUserId() : null;
      logger.info(`Token refresh event: success=${success}. New auth state: ${refreshedIsAuth}`);
      setIsAuthenticated(refreshedIsAuth);
      setUserId(refreshedUserId);
      // Also update global state on refresh
      appState.updateAuthState({
          isAuthenticated: refreshedIsAuth,
          isAuthLoading: false, // Refresh doesn't mean loading the whole app
          userId: refreshedUserId,
          // Don't clear lastAuthError here, refresh failure might set it
      });
    };
    tokenManager.addRefreshListener(handleRefresh);

    return () => {
      tokenManager.removeRefreshListener(handleRefresh);
    };
  }, [tokenManager]); // Rerun only if tokenManager instance changes

  // Login function
  const login = useCallback(async (credentials: LoginRequest): Promise<boolean> => {
    logger.info('Attempting login...');
    setIsAuthLoading(true);
    appState.updateAuthState({ isAuthLoading: true, lastAuthError: null });

    try {
      // 1. Call API
      const response: LoginResponse = await authApi.login(credentials.username, credentials.password);
      logger.info('Login API successful');

      // 2. Store Tokens
      const tokenData: TokenData = {
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        expiresAt: Date.now() + response.expiresIn * 1000,
        userId: response.userId,
      };
      tokenManager.storeTokens(tokenData);
      logger.info('Tokens stored');

      // Ensure device ID is registered with the session
      const deviceId = DeviceIdManager.getInstance().getDeviceId();
      logger.info(`Using device ID for this session: ${deviceId}`);

      // Update global app state
      appState.updateAuthState({
        isAuthenticated: true,
        isAuthLoading: false,
        userId: response.userId,
        lastAuthError: null,
      });

      // Update local context state
      setIsAuthenticated(true);
      setUserId(response.userId);
      setIsAuthLoading(false);
      logger.info('AuthContext state updated');

      return true;
    } catch (error: any) {
      logger.error("Login failed", { error: error.message });
      tokenManager.clearTokens(); // Ensure tokens are cleared

      // 5. Update global state on failure
      appState.updateAuthState({
        isAuthenticated: false,
        isAuthLoading: false, // Loading finished
        userId: null,
        lastAuthError: error?.message || 'Login failed',
      });

      // Update local context state
      setIsAuthenticated(false);
      setUserId(null);
      setIsAuthLoading(false);
      // Error handling (toast etc.) likely done by HttpClient/ErrorHandler

      return false; // Login failure
    }
  }, [authApi, tokenManager]); // Dependencies for useCallback

  // Logout function
  const logout = useCallback(async (): Promise<void> => {
    logger.info('Attempting logout...');
    setIsAuthLoading(true);
    appState.updateAuthState({ isAuthLoading: true });

    try {
      // First, stop the session via the ConnectionManager
      if (connectionManager) {
        try {
          // Call the ConnectionManager's stopSession method first
          const sessionStopped = await connectionManager.disconnect();
          logger.info(`Session ${sessionStopped ? 'successfully stopped' : 'stop request failed'}`);
        } catch (sessionError) {
          // Log but continue with logout process
          logger.warn('Failed to stop session via ConnectionManager:', { error: sessionError });
        }
      }

      // Then, disconnect the connection
      if (connectionManager) {
        connectionManager.disconnect('user_logout');
        logger.info('ConnectionManager disconnected');
      }

      // Now call the backend logout API if needed
      try {
        await authApi.logout();
        logger.info('Backend logout API call successful');
      } catch (apiError) {
        logger.error("Backend logout API call failed:", { error: apiError });
        // Continue with logout process regardless
      }

      // Finally, clear tokens and update state
      tokenManager.clearTokens();
      logger.info('Tokens cleared');

      // Update global state
      appState.updateAuthState({
        isAuthenticated: false,
        isAuthLoading: false,
        userId: null,
        lastAuthError: null,
      });

      // Update local context state
      setIsAuthenticated(false);
      setUserId(null);
      setIsAuthLoading(false);
      logger.info('Logout process completed');

    } catch (error) {
      logger.error("Unexpected error during logout process:", { error });
      
      // Ensure we still clear tokens and update state even if errors occur
      tokenManager.clearTokens();
      
      appState.updateAuthState({
        isAuthenticated: false,
        isAuthLoading: false,
        userId: null,
        lastAuthError: String(error),
      });
      
      setIsAuthenticated(false);
      setUserId(null);
      setIsAuthLoading(false);
    }
  }, [authApi, tokenManager, connectionManager]);

  // Memoize context value
  const contextValue = useMemo(() => ({
    isAuthenticated,
    isAuthLoading,
    userId,
    login,
    logout,
    tokenManager // Provide the instance
  }), [isAuthenticated, isAuthLoading, userId, login, logout, tokenManager]);

  // Render loading screen only during the very initial check
  // Avoid showing it on subsequent re-renders where loading might briefly be true
  const showInitialLoading = isAuthLoading && !isAuthenticated && userId === null;
  if (showInitialLoading) {
     return <LoadingSpinner message="Initializing session..." />;
  }

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};
