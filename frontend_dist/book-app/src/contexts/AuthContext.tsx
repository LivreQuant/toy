// frontend_dist/book-app/src/contexts/AuthContext.tsx
import React, { createContext, useState, useEffect, useCallback, ReactNode, useMemo } from 'react';

import { getLogger } from '@trading-app/logging';

import { AuthClient, LoginRequest, LoginResponse } from '@trading-app/api';

import { LoadingSpinner } from '@trading-app/ui';

import { authState } from '@trading-app/state';

import { toastService } from '@trading-app/toast';

import { TokenManager, TokenData } from '@trading-app/auth';
import { DeviceIdManager } from '@trading-app/auth';

import { config } from '@trading-app/config';

import { ConnectionManager } from '@trading-app/websocket';

const logger = getLogger('AuthContext');

interface AuthContextProps {
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  userId: string | number | null;
  login: (credentials: LoginRequest) => Promise<LoginResponse>;
  logout: () => Promise<void>;
  tokenManager: TokenManager;
  forgotPassword: (data: { email: string }) => Promise<boolean>;
}

export const AuthContext = createContext<AuthContextProps | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
  tokenManager: TokenManager;
  authApi: AuthClient;
  connectionManager: ConnectionManager;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ 
  children, 
  tokenManager, 
  authApi, 
  connectionManager 
}) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => tokenManager.isAuthenticated());
  const [isAuthLoading, setIsAuthLoading] = useState<boolean>(true);
  const [userId, setUserId] = useState<string | number | null>(() => tokenManager.getUserId());

  // Login function
  const login = useCallback(async (credentials: LoginRequest): Promise<LoginResponse> => {
    logger.info('🔍 AUTH: Attempting login...');
    console.log("🔍 AUTH: Login attempt for user:", credentials.username);
    
    setIsAuthLoading(true);
    authState.updateState({ isAuthLoading: true, lastAuthError: null });
  
    try {
      console.log("🔍 AUTH: Calling login API endpoint");
      const response = await authApi.login(credentials.username, credentials.password);
      console.log("🔍 AUTH: Raw API response:", JSON.stringify(response));
      
      console.log("🔍 AUTH: Response properties:", {
        success: response.success,
        requiresVerification: response.requiresVerification,
        userId: response.userId,
        error: response.error
      });
  
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
  
        const deviceId = DeviceIdManager.getInstance().getDeviceId();
        logger.info(`Using device ID for this session: ${deviceId}`);
  
        authState.updateState({
          isAuthenticated: true,
          isAuthLoading: false,
          userId: response.userId,
          lastAuthError: null,
        });
  
        setIsAuthenticated(true);
        setUserId(response.userId);

        // Start WebSocket connection immediately after successful login
        if (connectionManager) {
          logger.info('🔌 AUTH: Login successful, initiating WebSocket connection');
          connectionManager.setDesiredState({ 
            connected: true, 
            simulatorRunning: false 
          });
          
          setTimeout(async () => {
            logger.info('🔌 AUTH: Attempting to connect WebSocket after login');
            try {
              const connected = await connectionManager.connect();
              if (connected) {
                logger.info('🔌 AUTH: WebSocket connection established after login');
              } else {
                logger.warn('🔌 AUTH: WebSocket connection failed after login');
              }
            } catch (error: any) {
              logger.error('🔌 AUTH: Error connecting WebSocket after login', { error: error.message });
            }
          }, 100);
        }
      } else if (response.success) {
        logger.error("Login response marked as success but missing required data");
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
      tokenManager.clearTokens();
  
      authState.updateState({
        isAuthenticated: false,
        isAuthLoading: false,
        userId: null,
        lastAuthError: error?.message || 'Login failed',
      });
  
      setIsAuthenticated(false);
      setUserId(null);
      setIsAuthLoading(false);
  
      return {
        success: false,
        error: error?.message || 'Login failed'
      };
    }
  }, [authApi, tokenManager, connectionManager]);

  // Check authentication status on mount and sync global state
  useEffect(() => {
    const checkAuth = async () => {
      // Normal authentication check for existing tokens
      const authenticated = tokenManager.isAuthenticated();
      const currentUserId = authenticated ? tokenManager.getUserId() : null;
      logger.info(`Initial auth check: authenticated=${authenticated}, userId=${currentUserId}`);
      setIsAuthenticated(authenticated);
      setUserId(currentUserId);
      
      // Sync global state on initial load
      authState.updateState({
          isAuthenticated: authenticated,
          isAuthLoading: false,
          userId: currentUserId,
          lastAuthError: null
      });
      setIsAuthLoading(false);

      // Auto-connect WebSocket when authenticated
      if (authenticated && connectionManager) {
        logger.info('🔌 AUTH: User is authenticated, setting up WebSocket connection');
        connectionManager.setDesiredState({ 
          connected: true, 
          simulatorRunning: false 
        });
      }
    };
    
    checkAuth();

    // Listen for token refresh events to update auth state
    const handleRefresh = (success: boolean) => {
      const refreshedIsAuth = success && tokenManager.isAuthenticated();
      const refreshedUserId = refreshedIsAuth ? tokenManager.getUserId() : null;
      logger.info(`Token refresh event: success=${success}. New auth state: ${refreshedIsAuth}`);
      setIsAuthenticated(refreshedIsAuth);
      setUserId(refreshedUserId);
      
      authState.updateState({
          isAuthenticated: refreshedIsAuth,
          isAuthLoading: false,
          userId: refreshedUserId,
      });

      // Reconnect WebSocket after token refresh
      if (refreshedIsAuth && connectionManager) {
        logger.info('🔌 AUTH: Token refreshed successfully, ensuring WebSocket connection');
        connectionManager.setDesiredState({ 
          connected: true, 
          simulatorRunning: false 
        });
      }
    };
    tokenManager.addRefreshListener(handleRefresh);

    return () => {
      tokenManager.removeRefreshListener(handleRefresh);
    };
  }, [tokenManager, connectionManager]);

  const forgotPassword = useCallback(async (data: { email: string }): Promise<boolean> => {
    logger.info('Attempting forgot password...');
    setIsAuthLoading(true);
    
    try {
      const response = await authApi.forgotPassword(data);
      setIsAuthLoading(false);
      return true;
    } catch (error: any) {
      logger.error("Forgot password failed", { error: error.message });
      setIsAuthLoading(false);
      return false;
    }
  }, [authApi]);

  const logout = useCallback(async (): Promise<void> => {
    logger.info('🔌 AUTH: Attempting logout...');
    setIsAuthLoading(true);
    authState.updateState({ isAuthLoading: true });
  
    try {
      // Disconnect WebSocket FIRST before logout
      if (connectionManager) {
        try {
          logger.info('🔌 AUTH: Disconnecting WebSocket before logout');
          connectionManager.setDesiredState({ 
            connected: false,
            simulatorRunning: false 
          });
          await connectionManager.disconnect('user_logout');
          logger.info('🔌 AUTH: WebSocket disconnected for logout');
        } catch (sessionError) {
          logger.warn('🔌 AUTH: Failed to disconnect WebSocket during logout:', { error: sessionError });
        }
      }
      
      try {
        await authApi.logout();
        logger.info('Backend logout API call successful');
      } catch (apiError) {
        logger.error("Backend logout API call failed:", { error: apiError });
      }
  
      tokenManager.clearTokens();
      logger.info('Tokens cleared');
  
      authState.updateState({
        isAuthenticated: false,
        isAuthLoading: false,
        userId: null,
        lastAuthError: null,
      });
  
      setIsAuthenticated(false);
      setUserId(null);
      setIsAuthLoading(false);
      logger.info('Logout process completed');
  
      toastService.success('You have been successfully logged out');
      
      // Redirect to land app after logout
      const landAppUrl = config.gateway.baseUrl;
      logger.info('🔗 AUTH: Redirecting to land app after logout', { landAppUrl });
      window.location.href = landAppUrl;
      
    } catch (error) {
      logger.error("Unexpected error during logout process:", { error });
      toastService.error(`Logout error: ${error instanceof Error ? error.message : 'Unknown error'}`);
      
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
  
      // Even on error, redirect to land app
      const landAppUrl = config.gateway.baseUrl;
      logger.info('🔗 AUTH: Redirecting to land app after logout error', { landAppUrl });
      window.location.href = landAppUrl;
    }
  }, [authApi, tokenManager, connectionManager]);

  // Development helpers - expose to window in dev mode
  useEffect(() => {
    if (process.env.NODE_ENV === 'development') {
      (window as any).devAuth = {
        manualLogin: async (username?: string, password?: string) => {
          const user = username || prompt('Enter username:');
          const pass = password || prompt('Enter password:');
          if (user && pass) {
            return await login({ username: user, password: pass });
          }
        },
        showCurrentAuth: () => {
          console.log('🔍 Current Auth Status:');
          console.log(`Authenticated: ${isAuthenticated}`);
          console.log(`User ID: ${userId}`);
          console.log(`Tokens:`, tokenManager.getTokens());
        },
        clearAuth: () => {
          tokenManager.clearTokens();
          console.log('🗑️ Authentication cleared. Refresh the page.');
        },
        tokenManager: {
          isAuthenticated: () => tokenManager.isAuthenticated(),
          getUserId: () => tokenManager.getUserId(),
          getTokens: () => tokenManager.getTokens(),
          clearTokens: () => tokenManager.clearTokens(),
          getAccessToken: async () => await tokenManager.getAccessToken(),
          getCsrfToken: async () => await tokenManager.getCsrfToken()
        }
      };
      
      console.log('🔧 DEV MODE: Global devAuth helper available');
      console.log('Usage:');
      console.log('  devAuth.showCurrentAuth() - Show current auth state');
      console.log('  devAuth.manualLogin() - Login with prompts');
      console.log('  devAuth.manualLogin("user", "pass") - Direct login');
      console.log('  devAuth.clearAuth() - Clear authentication');
      console.log('  devAuth.tokenManager - Access token manager methods');
    }
  }, [isAuthenticated, userId, login, tokenManager]);

  const contextValue = useMemo(() => ({
    isAuthenticated,
    isAuthLoading,
    userId,
    login,
    logout,
    tokenManager,
    forgotPassword
  }), [isAuthenticated, isAuthLoading, userId, login, logout, tokenManager, forgotPassword]);

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