// src/contexts/AuthContext.tsx
import React, {
  createContext,
  useState,
  useContext,
  useEffect,
  useMemo,
  useCallback,
  ReactNode,
} from 'react';

// --- Import Services and APIs ---
import { TokenManager, TokenData } from '../services/auth/token-manager';
import { LocalStorageService } from '../services/storage/local-storage-service';
import { ErrorHandler } from '../utils/error-handler';
import { Logger } from '../utils/logger';
import { HttpClient } from '../api/http-client';
import { AuthApi, LoginResponse } from '../api/auth';
import { toastService } from '../services/notification/toast-service'; // For ErrorHandler

// Define the shape of the context data
interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean; // To indicate initial auth check
  user: { id: string | number } | null; // Basic user info (extend as needed)
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  // Optionally expose tokenManager or authApi if needed by advanced components
  // tokenManagerInstance: TokenManager | null;
  // authApiInstance: AuthApi | null;
}

// Create the context with a default value
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Define props for the provider (only children)
interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true); // Start loading initially
  const [user, setUser] = useState<{ id: string | number } | null>(null);

  // --- Instantiate Services within the Provider ---
  // Use useMemo to ensure services are created only once per provider instance
  const services = useMemo(() => {
    console.log("Instantiating AuthContext services..."); // Log instantiation
    const logger = Logger.getInstance().createChild('AuthContext'); // Get logger instance
    const storageService = new LocalStorageService();
    // ErrorHandler needs logger and toastService
    const errorHandler = new ErrorHandler(logger, toastService);
    // TokenManager needs storageService and errorHandler
    const tokenManager = new TokenManager(storageService, errorHandler);
    // HttpClient needs tokenManager
    const httpClient = new HttpClient(tokenManager);
    // AuthApi needs httpClient
    const authApi = new AuthApi(httpClient);
    // Resolve circular dependency: Give TokenManager the AuthApi instance
    tokenManager.setAuthApi(authApi);

    return { logger, tokenManager, authApi, errorHandler };
  }, []); // Empty dependency array ensures this runs only once

  // --- Authentication Logic ---

  // Function to check authentication status (can be called on mount and after login/logout)
  const checkAuthStatus = useCallback(async () => {
    setIsLoading(true);
    try {
      // Use getAccessToken which handles refresh internally if needed
      const token = await services.tokenManager.getAccessToken();
      const authStatus = !!token; // Check if token exists and is valid (getAccessToken returns null if invalid/refresh fails)
      setIsAuthenticated(authStatus);
      if (authStatus) {
        const userId = services.tokenManager.getUserId();
        setUser(userId ? { id: userId } : null);
        services.logger.info('User is authenticated.', { userId });
      } else {
        setUser(null);
        services.logger.info('User is not authenticated.');
        // Ensure tokens are cleared if check fails after potential refresh attempt
        services.tokenManager.clearTokens();
      }
    } catch (error) {
      services.logger.error('Error checking auth status', { error });
      setIsAuthenticated(false);
      setUser(null);
      services.tokenManager.clearTokens(); // Clear tokens on error
    } finally {
      setIsLoading(false);
    }
  }, [services]); // Dependency on services object

  // Check authentication status on initial mount
  useEffect(() => {
    services.logger.info('AuthContext mounted. Checking initial auth status...');
    checkAuthStatus();
  }, [checkAuthStatus, services.logger]); // Depend on checkAuthStatus callback

  // Login function
  const login = useCallback(async (username: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    try {
      services.logger.info('Attempting login...');
      const response: LoginResponse = await services.authApi.login(username, password);
      // Store tokens immediately after successful login
      const tokenData: TokenData = {
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        expiresAt: Date.now() + response.expiresIn * 1000,
        userId: response.userId,
      };
      services.tokenManager.storeTokens(tokenData);
      // Update state after storing tokens
      setIsAuthenticated(true);
      setUser({ id: response.userId });
      services.logger.info('Login successful.', { userId: response.userId });
      setIsLoading(false);
      return true;
    } catch (error: any) {
      services.logger.error('Login failed', { error: error.message });
      // Use errorHandler to display appropriate message
      services.errorHandler.handleAuthError(
        error instanceof Error ? error : new Error('Login failed'),
        undefined, // Default severity
        'AuthContext.login'
      );
      setIsAuthenticated(false);
      setUser(null);
      services.tokenManager.clearTokens(); // Ensure tokens are cleared on failed login
      setIsLoading(false);
      return false;
    }
  }, [services]); // Dependency on services

  // Logout function
  const logout = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    try {
      services.logger.info('Attempting logout...');
      // Attempt server-side logout first (optional, might fail if token expired)
      await services.authApi.logout();
      services.logger.info('Server-side logout successful (or ignored).');
    } catch (error: any) {
      // Log API logout error but proceed with client-side cleanup
      services.logger.warn('Server-side logout failed (might be expected if token expired)', { error: error.message });
    } finally {
      // Always perform client-side cleanup
      services.tokenManager.clearTokens();
      setIsAuthenticated(false);
      setUser(null);
      setIsLoading(false);
      services.logger.info('Client-side logout completed.');
      // Optional: Redirect to login page after state update
      // window.location.href = '/login'; // Consider using react-router-dom navigation
    }
  }, [services]); // Dependency on services

  // --- Context Value ---
  const contextValue = useMemo(
    () => ({
      isAuthenticated,
      isLoading,
      user,
      login,
      logout,
      // tokenManagerInstance: services.tokenManager, // Expose if needed
      // authApiInstance: services.authApi, // Expose if needed
    }),
    [isAuthenticated, isLoading, user, login, logout /*, services */] // Include services if exposing instances
  );


  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

// Custom hook to use the AuthContext
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
