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
import { BehaviorSubject } from 'rxjs';

// --- Import Services and APIs ---
import { TokenManager, TokenData } from '../services/auth/token-manager';
import { LocalStorageService } from '../services/storage/local-storage-service';
import { HttpClient } from '../api/http-client';
import { AuthApi, LoginResponse } from '../api/auth';
import { toastService } from '../services/notification/toast-service';
import { AppErrorHandler } from '../utils/app-error-handler';
import { ErrorSeverity } from '../utils/error-handler';
import { appState } from '../services/state/app-state.service';
import { getLogger } from '../boot/logging';

// Define the shape of the context data
interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: { id: string | number } | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
}

// Create the context with a default value
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Define props for the provider
interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [user, setUser] = useState<{ id: string | number } | null>(null);
  
  // Create a logger for AuthContext
  const logger = getLogger('AuthContext');

  // --- Instantiate Services within the Provider ---
  const services = useMemo(() => {
    logger.info("Instantiating AuthContext services...");
    const storageService = new LocalStorageService();

    // Instantiate TokenManager
    const tokenManager = new TokenManager(storageService, AppErrorHandler.getInstance());
    
    // Instantiate HttpClient with TokenManager
    const httpClient = new HttpClient(tokenManager);
    
    // Instantiate AuthApi with HttpClient
    const authApi = new AuthApi(httpClient);
    
    // Resolve circular dependency after all instances are created
    tokenManager.setAuthApi(authApi);

    return { tokenManager, authApi };
  }, []);

  // Authentication status observable
  const authState$ = useMemo(() => new BehaviorSubject({
    isAuthenticated: false,
    isLoading: true,
    userId: null as string | number | null
  }), []);

  // --- Authentication Logic ---

  // Function to check authentication status
  const checkAuthStatus = useCallback(async () => {
    setIsLoading(true);
    try {
      // Use getAccessToken which handles refresh internally if needed
      const token = await services.tokenManager.getAccessToken();
      const authStatus = !!token;
      
      // Update local React state
      setIsAuthenticated(authStatus);
      
      if (authStatus) {
        const userId = services.tokenManager.getUserId();
        setUser(userId ? { id: userId } : null);
        logger.info('User is authenticated.', { userId });
        
        // Update the reactive app state
        appState.updateAuth({
          isAuthenticated: true,
          isLoading: false,
          userId
        });
        
        // Update the auth state observable
        authState$.next({
          isAuthenticated: true,
          isLoading: false,
          userId
        });
      } else {
        setUser(null);
        logger.info('User is not authenticated.');
        services.tokenManager.clearTokens();
        
        // Update the reactive app state
        appState.updateAuth({
          isAuthenticated: false,
          isLoading: false,
          userId: null
        });
        
        // Update the auth state observable
        authState$.next({
          isAuthenticated: false,
          isLoading: false,
          userId: null
        });
      }
    } catch (error) {
      logger.error('Error checking auth status', { error });
      setIsAuthenticated(false);
      setUser(null);
      services.tokenManager.clearTokens();
      
      // Update reactive state on error
      appState.updateAuth({
        isAuthenticated: false,
        isLoading: false,
        userId: null
      });
      
      // Update the auth state observable
      authState$.next({
        isAuthenticated: false,
        isLoading: false,
        userId: null
      });
    } finally {
      setIsLoading(false);
    }
  }, [services, authState$]);

  // Check authentication status on initial mount
  useEffect(() => {
    logger.info('AuthContext mounted. Checking initial auth status...');
    checkAuthStatus();
    
    // Cleanup function
    return () => {
      // If needed, perform any cleanup here
      logger.info('AuthContext unmounting...');
    };
  }, [checkAuthStatus]);

  // Login function
  const login = useCallback(async (username: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    
    // Update app state
    appState.updateAuth({
      isLoading: true
    });
    
    // Update observable
    authState$.next({
      ...authState$.getValue(),
      isLoading: true
    });
    
    try {
      logger.info('Attempting login...');
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
      logger.info('Login successful.', { userId: response.userId });
      
      // Update reactive app state
      appState.updateAuth({
        isAuthenticated: true,
        isLoading: false,
        userId: response.userId
      });
      
      // Update the auth state observable
      authState$.next({
        isAuthenticated: true,
        isLoading: false,
        userId: response.userId
      });
      
      setIsLoading(false);
      return true;
    } catch (error: any) {
      logger.error('Login failed', { error: error.message });
      
      // Use errorHandler to display appropriate message
      AppErrorHandler.handleAuthError(
        error instanceof Error ? error : new Error('Login failed'),
        ErrorSeverity.MEDIUM,
        'AuthContext.login'
      );
      
      setIsAuthenticated(false);
      setUser(null);
      services.tokenManager.clearTokens();

      // src/contexts/AuthContext.tsx (continued)
      // Update reactive app state
      appState.updateAuth({
        isAuthenticated: false,
        isLoading: false,
        userId: null
      });
      
      // Update the auth state observable
      authState$.next({
        isAuthenticated: false,
        isLoading: false,
        userId: null
      });
      
      setIsLoading(false);
      return false;
    }
  }, [services, authState$, logger]);

  // Logout function
  const logout = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    
    // Update app state
    appState.updateAuth({
      isLoading: true
    });
    
    // Update observable
    authState$.next({
      ...authState$.getValue(),
      isLoading: true
    });
    
    try {
      logger.info('Attempting logout...');
      // Attempt server-side logout first (optional, might fail if token expired)
      await services.authApi.logout();
      logger.info('Server-side logout successful.');
    } catch (error: any) {
      // Log API logout error but proceed with client-side cleanup
      logger.warn('Server-side logout failed (might be expected if token expired)', { error: error.message });
    } finally {
      // Always perform client-side cleanup
      services.tokenManager.clearTokens();
      setIsAuthenticated(false);
      setUser(null);
      
      // Update reactive app state
      appState.updateAuth({
        isAuthenticated: false,
        isLoading: false,
        userId: null
      });
      
      // Update the auth state observable
      authState$.next({
        isAuthenticated: false,
        isLoading: false,
        userId: null
      });
      
      setIsLoading(false);
      logger.info('Client-side logout completed.');
      
      // Clear other app state
      appState.update({
        connection: {
          ...appState.getState().connection,
          status: 'DISCONNECTED',
          quality: 'UNKNOWN',
          simulatorStatus: 'UNKNOWN'
        },
        exchange: {
          data: {},
          lastUpdated: 0
        },
        portfolio: {
          positions: {},
          orders: {},
          cash: 0,
          lastUpdated: 0
        }
      });
    }
  }, [services, authState$, logger]);

  // --- Context Value ---
  const contextValue = useMemo(
    () => ({
      isAuthenticated,
      isLoading,
      user,
      login,
      logout,
    }),
    [isAuthenticated, isLoading, user, login, logout]
  );

  // Provide a way to subscribe to auth state changes
  useEffect(() => {
    // This effect makes the authentication state observable available to external components
    // that want to use RxJS directly instead of React context
    return () => {
      // No cleanup needed for BehaviorSubject
    };
  }, [authState$]);

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

// Export the auth state observable for components that prefer using RxJS directly
export const getAuthStateObservable = () => {
  // This should be accessed after AuthProvider has been initialized
  return (window as any).__authState$ || new BehaviorSubject({
    isAuthenticated: false,
    isLoading: true,
    userId: null as string | number | null
  });
};