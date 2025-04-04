import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  useCallback // Added useCallback
} from 'react';
import { TokenManager, TokenData } from '../services/auth/token-manager';
import { AuthApi, LoginResponse } from '../api/auth';
import { HttpClient } from '../api/http-client';
import { ConnectionManager } from '../services/connection/connection-manager';
import { Logger } from '../utils/logger';
import { SessionManager } from '../services/session/session-manager';
import { LocalStorageService } from '../services/storage/local-storage-service'; // Assuming path
import { toastService } from '../services/notification/toast-service'; // For error notifications

// Define the shape of the user object provided by the context
interface User {
    id: string | number;
    // Add other relevant user details if available (e.g., username, roles)
}

// Define the shape of the authentication context
interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  tokenManager: TokenManager;
  sessionManager: SessionManager;
  connectionManager: ConnectionManager;
  login: (username: string, password: string) => Promise<boolean>;
  logout: (reason?: string) => Promise<void>; // Add optional reason
}

// Create the context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * Provides authentication state and services to the application.
 * Manages user login, logout, token handling, and related services.
 */
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // --- Service Instantiation ---
  // Use useState with initializer function to create instances only once
  const [logger] = useState<Logger>(() => Logger.getInstance());
  const [storageService] = useState<LocalStorageService>(() => new LocalStorageService());
  const [sessionManager] = useState<SessionManager>(() => new SessionManager(storageService, logger));
  const [tokenManager] = useState<TokenManager>(() => {
      const tm = new TokenManager();
      // Perform initial setup like setting AuthApi if needed immediately
      // Note: httpClient needs tokenManager, so initialization order matters
      return tm;
  });
  const [httpClient] = useState<HttpClient>(() => new HttpClient(tokenManager /*, logger */)); // Pass logger if HttpClient accepts it
  const [authApi] = useState<AuthApi>(() => new AuthApi(httpClient));
  const [connectionManager] = useState<ConnectionManager>(() => new ConnectionManager(tokenManager, logger)); // Pass logger

  // --- State Variables ---
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true); // Start loading until initial check completes
  const [user, setUser] = useState<User | null>(null);

  // --- Initial Authentication Check Effect ---
  useEffect(() => {
    logger.info('AuthContext: Performing initial authentication check...');
    // Set AuthApi dependency in TokenManager *after* both are instantiated
    tokenManager.setAuthApi(authApi);

    const checkAuthStatus = async () => {
      setIsLoading(true);
      const currentTokens = tokenManager.getTokens();
      let authenticated = false;
      let userId: string | number | null = null;

      if (currentTokens) {
        logger.info('AuthContext: Found existing tokens.');
        // Optional: Add token validation logic here if needed (e.g., call a backend endpoint)
        // For simplicity, we assume tokens are valid if they exist and haven't expired locally
        if (currentTokens.expiresAt > Date.now()) {
            logger.info('AuthContext: Existing tokens appear valid.');
            authenticated = true;
            userId = currentTokens.userId;
        } else {
             logger.warn('AuthContext: Existing tokens expired. Attempting refresh...');
             // Try refreshing the token if expired
             const refreshed = await tokenManager.refreshAccessToken();
             if (refreshed) {
                 logger.info('AuthContext: Token refresh successful.');
                 const refreshedTokens = tokenManager.getTokens(); // Get newly stored tokens
                 if (refreshedTokens) {
                    authenticated = true;
                    userId = refreshedTokens.userId;
                 }
             } else {
                 logger.error('AuthContext: Token refresh failed.');
                 tokenManager.clearTokens(); // Clear invalid/expired tokens
                 sessionManager.clearSession(); // Clear session if refresh fails
             }
        }
      } else {
        logger.info('AuthContext: No existing tokens found.');
      }

      setIsAuthenticated(authenticated);
      setUser(authenticated && userId ? { id: userId } : null);
      setIsLoading(false);
      logger.info(`AuthContext: Initial check complete. Authenticated: ${authenticated}`);

      // Automatically connect if authenticated after initial check
      if (authenticated) {
          logger.info("AuthContext: Attempting initial connection after successful auth check.");
          connectionManager.connect().catch(err => {
              logger.error("AuthContext: Initial connection attempt failed.", err);
          });
      }
    };

    checkAuthStatus();

    // --- Listener for Forced Logout ---
    // This handles cases where the connection manager detects an unrecoverable auth issue
    const handleForceLogout = (reason: string) => {
        logger.warn(`AuthContext: Handling force_logout event. Reason: ${reason}`);
        // Update state to reflect logout
        setIsAuthenticated(false);
        setUser(null);
        // No need to clear tokens/session here, assume the source of the event did that.
        toastService.error(`Logged out: ${reason}`, 10000); // Notify user
    };
    connectionManager.on('force_logout', handleForceLogout);

    // Cleanup listener on component unmount
    return () => {
      connectionManager.off('force_logout', handleForceLogout);
      // Optional: Disconnect connection manager on AuthProvider unmount?
      // connectionManager.dispose(); // Or disconnect()
    };
    // Ensure dependencies cover all used external variables/functions
  }, [connectionManager, tokenManager, sessionManager, authApi, httpClient, logger]); // Added dependencies

  // --- Login Function ---
  const login = useCallback(async (username: string, password: string): Promise<boolean> => {
    logger.info(`AuthContext: Attempting login for user: ${username}`);
    setIsLoading(true);
    try {
      const response: LoginResponse = await authApi.login(username, password);
      tokenManager.storeTokens({
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        expiresAt: Date.now() + (response.expiresIn * 1000),
        userId: response.userId
      });
      setIsAuthenticated(true);
      setUser({ id: response.userId });
      logger.info(`AuthContext: Login successful for user ID: ${response.userId}`);
      // Attempt connection after successful login
      await connectionManager.connect();
      setIsLoading(false);
      return true;
    } catch (error: any) {
      logger.error("AuthContext: Login failed", { error: error.message });
      // Ensure state reflects failed login
      setIsAuthenticated(false);
      setUser(null);
      tokenManager.clearTokens(); // Clear any potentially partially stored tokens
      sessionManager.clearSession(); // Clear session on login failure
      setIsLoading(false);
      toastService.error(`Login failed: ${error.message || 'Please check credentials'}`);
      return false;
    }
  }, [authApi, tokenManager, connectionManager, sessionManager, logger]); // Dependencies for login

  // --- Logout Function ---
  const logout = useCallback(async (reason: string = 'user_request'): Promise<void> => {
    logger.warn(`AuthContext: Logout requested. Reason: ${reason}`);
    setIsLoading(true); // Optional: show loading during logout

    // 1. Disconnect services
    connectionManager.disconnect(`logout: ${reason}`);

    // 2. Attempt backend logout (optional, but good practice)
    try {
      await authApi.logout();
      logger.info("AuthContext: Backend logout successful.");
    } catch (error: any) {
      // Log backend error but proceed with client-side cleanup
      logger.error("AuthContext: Backend logout failed (continuing client-side)", { error: error.message });
    } finally {
      // 3. Clear client-side tokens and session
      tokenManager.clearTokens();
      sessionManager.clearSession(); // Use instance method

      // 4. Update application state
      setIsAuthenticated(false);
      setUser(null);
      setIsLoading(false);
      logger.info("AuthContext: Client-side logout complete.");
    }
  }, [authApi, tokenManager, connectionManager, sessionManager, logger]); // Dependencies for logout

  // --- Context Value ---
  // Memoize the context value to prevent unnecessary re-renders
  const contextValue = useMemo(() => ({
    isAuthenticated,
    isLoading,
    user,
    tokenManager,
    sessionManager, // Provide the instance
    connectionManager, // Provide the instance
    login,
    logout,
  }), [
      isAuthenticated,
      isLoading,
      user,
      tokenManager,
      sessionManager, // Include instances in dependency array
      connectionManager, // Include instances in dependency array
      login,
      logout
    ]);

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

/**
 * Custom hook to easily access the AuthContext.
 * Ensures the hook is used within a component wrapped by AuthProvider.
 */
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

