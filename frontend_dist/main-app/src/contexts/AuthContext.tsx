// Likely inside src/contexts/AuthContext.tsx
import React, { createContext, useState, useEffect, useCallback, ReactNode, useMemo } from 'react';

import { getLogger } from '../boot/logging'; // Adjust path as needed

import { AuthApi } from '../api/auth'; // Adjust path as needed
import { LoginRequest, LoginResponse } from '@trading-app/auth';

import LoadingSpinner from '../components/Common/LoadingSpinner'; // Assuming component exists

import { authState } from '../state/auth-state';

import { toastService } from '../services/notification/toast-service';

import { TokenManager, TokenData } from '../services/auth/token-manager'; // Adjust path
import { DeviceIdManager } from '../services/auth/device-id-manager';

import { ConnectionManager } from '@trading-app/websocket';


const logger = getLogger('AuthContext'); // Initialize logger for this context

interface AuthContextProps {
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  userId: string | number | null;
  login: (credentials: LoginRequest) => Promise<LoginResponse>; // Updated return type
  logout: () => Promise<void>;
  tokenManager: TokenManager;
  forgotPassword: (data: { email: string }) => Promise<boolean>;
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
      authState.updateState({
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
      authState.updateState({
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
  const login = useCallback(async (credentials: LoginRequest): Promise<LoginResponse> => {
    logger.info('🔍 AUTH: Attempting login...');
    console.log("🔍 AUTH: Login attempt for user:", credentials.username);
    
    setIsAuthLoading(true);
    authState.updateState({ isAuthLoading: true, lastAuthError: null });
  
    try {
      // 1. Call API
      console.log("🔍 AUTH: Calling login API endpoint");
      const response = await authApi.login(credentials.username, credentials.password);
      console.log("🔍 AUTH: Raw API response:", JSON.stringify(response));
      
      // Log detailed response properties
      console.log("🔍 AUTH: Response properties:", {
        success: response.success,
        requiresVerification: response.requiresVerification,
        userId: response.userId,
        error: response.error
      });
  
      // If we get a requiresVerification flag, return early
      if (response.requiresVerification) {
        console.log("🔍 AUTH: Login requires email verification for userId:", response.userId);
        setIsAuthLoading(false);
        
        authState.updateState({
          isAuthenticated: false,
          isAuthLoading: false,
          userId: response.userId || null,
          lastAuthError: 'Email verification required'
        });
        
        return response;
      }
  
      // 2. Store Tokens - only do this if login was successful and all required fields are present
      if (response.success && 
          response.accessToken && 
          response.refreshToken && 
          response.expiresIn && 
          response.userId) {
        
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
        authState.updateState({
          isAuthenticated: true,
          isAuthLoading: false,
          userId: response.userId,
          lastAuthError: null,
        });
  
        // Update local context state
        setIsAuthenticated(true);
        setUserId(response.userId);
      } else if (response.success) {
        // Success but missing data
        logger.error("Login response marked as success but missing required data");
        
        // Return a failed response
        return {
          success: false,
          error: "Missing authentication data from server"
        };
      }
      
      setIsAuthLoading(false);
      logger.info('AuthContext state updated');
  
      return response;
    } catch (error: any) {
      logger.error("Login failed", { error: error.message });
      tokenManager.clearTokens(); // Ensure tokens are cleared
  
      // Update global state on failure
      authState.updateState({
        isAuthenticated: false,
        isAuthLoading: false,
        userId: null,
        lastAuthError: error?.message || 'Login failed',
      });
  
      // Update local context state
      setIsAuthenticated(false);
      setUserId(null);
      setIsAuthLoading(false);
  
      return {
        success: false,
        error: error?.message || 'Login failed'
      };
    }
  }, [authApi, tokenManager]);

  const forgotPassword = useCallback(async (data: { email: string }): Promise<boolean> => {
    logger.info('Attempting forgot password...');
    setIsAuthLoading(true);
    
    try {
      // Call API (implement this if the API exists, otherwise simulate it)
      const response = await authApi.forgotPassword(data);
      
      setIsAuthLoading(false);
      return true;
    } catch (error: any) {
      logger.error("Forgot password failed", { error: error.message });
      setIsAuthLoading(false);
      return false;
    }
  }, [authApi]);

  // Logout function
  const logout = useCallback(async (): Promise<void> => {
    logger.info('Attempting logout...');
    setIsAuthLoading(true);
    authState.updateState({ isAuthLoading: true });

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
        try {
          // Call the ConnectionManager's disconnect method first
          await connectionManager.disconnect('user_logout');
          logger.info('ConnectionManager disconnected');
          
          // IMPORTANT: Reset the ConnectionManager's desired state
          connectionManager.setDesiredState({ 
            connected: false,
            simulatorRunning: false 
          });
        } catch (sessionError) {
          logger.warn('Failed to disconnect ConnectionManager:', { error: sessionError });
        }
      }

      if (connectionManager) {
        connectionManager.resetState();
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
      authState.updateState({
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

      // Show success toast
      toastService.success('You have been successfully logged out');
      
    } catch (error) {
      logger.error("Unexpected error during logout process:", { error });
        
      // Show error toast
      toastService.error(`Logout error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      
      // Ensure we still clear tokens and update state even if errors occur
      tokenManager.clearTokens();
      
      authState.updateState({
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
    tokenManager,
    forgotPassword // Add this property
  }), [isAuthenticated, isAuthLoading, userId, login, logout, tokenManager, forgotPassword]);

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
