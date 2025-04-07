// src/contexts/ConnectionContext.tsx
import React, { useContext, useEffect, useRef, ReactNode } from 'react';
import { ConnectionManager, ConnectionDesiredState } from '../services/connection/connection-manager';
import { TokenManager } from '../services/auth/token-manager';
import { getLogger } from '../boot/logging';
import { useAppState } from '../hooks/useAppState';
import { appState } from '../services/state/app-state.service';
import { Disposable } from '../utils/disposable';
import { AppErrorHandler } from '../utils/app-error-handler';
import { ErrorSeverity } from '../utils/error-handler';
import { useAuth } from './AuthContext';

// Define the context interface
export interface ConnectionContextType {
  // Connection Actions
  setDesiredState: (state: Partial<ConnectionDesiredState>) => void;
  manualReconnect: () => Promise<boolean>;
  
  // Order Actions
  submitOrder: ConnectionManager['submitOrder'];
  cancelOrder: ConnectionManager['cancelOrder'];
  
  // Simulator Actions
  startSimulator: ConnectionManager['startSimulator'];
  stopSimulator: ConnectionManager['stopSimulator'];
}

// Create context with default values
const ConnectionContext = createContext<ConnectionContextType>({
  setDesiredState: () => {},
  manualReconnect: async () => false,
  submitOrder: async () => ({ success: false, error: "Not initialized" }),
  cancelOrder: async () => ({ success: false, error: "Not initialized" }),
  startSimulator: async () => ({ success: false, error: "Not initialized" }),
  stopSimulator: async () => ({ success: false, error: "Not initialized" }),
});

interface ConnectionProviderProps {
  children: ReactNode;
  tokenManager: TokenManager;
  logger: any; // Accept both Logger and EnhancedLogger
}

export const ConnectionProvider: React.FC<ConnectionProviderProps> = ({ 
  children, 
  tokenManager
}) => {
  const logger = getLogger('ConnectionContext');
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const connectionManagerRef = useRef<ConnectionManager | null>(null);
  const isInitializedRef = useRef(false);
  
  // Effect to initialize or clean up ConnectionManager based on auth state
  useEffect(() => {
    logger.info(`Auth status changed: isAuthenticated=${isAuthenticated}, isLoading=${isAuthLoading}`);
    
    // Don't do anything while auth is still loading
    if (isAuthLoading) {
      logger.info("Auth still loading, waiting...");
      return;
    }
    
    // CASE 1: User is authenticated - initialize connection if needed
    if (isAuthenticated) {
      logger.info("User is authenticated, initializing connection services");
      
      if (!connectionManagerRef.current && !isInitializedRef.current) {
        logger.info("Creating new ConnectionManager instance");
        isInitializedRef.current = true;
        
        // Create ConnectionManager
        const newConnectionManager = new ConnectionManager(tokenManager, { 
          // options if needed
        });
        connectionManagerRef.current = newConnectionManager;
        
        // Auto-connect after a short delay
        const connectionTimer = setTimeout(() => {
          if (connectionManagerRef.current) {
            logger.info("Setting initial desired state");
            connectionManagerRef.current.setDesiredState({ connected: true });
          }
        }, 500);
        
        return () => {
          clearTimeout(connectionTimer);
        };
      }
      
      return;
    }
    
    // CASE 2: User is not authenticated - clean up connection
    logger.info("User is not authenticated, cleaning up connection services");
    
    if (connectionManagerRef.current) {
      logger.warn("Disposing ConnectionManager due to auth change");
      const manager = connectionManagerRef.current;
      
      // Update desired state to disconnect
      manager.setDesiredState({ connected: false, simulatorRunning: false });
      
      // Allow time for graceful disconnection before disposal
      const disposeTimer = setTimeout(() => {
        manager.dispose();
        connectionManagerRef.current = null;
        isInitializedRef.current = false;
        
        // Reset connection state in the reactive store
        appState.updateConnection({
          status: 'DISCONNECTED',
          quality: 'UNKNOWN',
          isRecovering: false,
          recoveryAttempt: 0,
          simulatorStatus: 'UNKNOWN',
        });
      }, 300);

      return () => {
        clearTimeout(disposeTimer);
      };
    }
  }, [isAuthenticated, isAuthLoading, tokenManager, logger]);
  
  // Effect to clean up on unmount
  useEffect(() => {
    return () => {
      if (connectionManagerRef.current) {
        logger.warn("Cleaning up ConnectionManager on unmount");
        connectionManagerRef.current.dispose();
        connectionManagerRef.current = null;
        isInitializedRef.current = false;
      }
    };
  }, [logger]);

  // Action callbacks
  const setDesiredState = React.useCallback((state: Partial<ConnectionDesiredState>): void => {
    if (connectionManagerRef.current) {
      logger.info(`Setting desired state: ${JSON.stringify(state)}`);
      connectionManagerRef.current.setDesiredState(state);
    } else {
      logger.warn("setDesiredState called but ConnectionManager not initialized");
    }
  }, [logger]);

  const manualReconnect = React.useCallback(async (): Promise<boolean> => {
    if (!connectionManagerRef.current) {
      logger.error("Manual reconnect failed: ConnectionManager not initialized");
      AppErrorHandler.handleConnectionError("Connection service unavailable", ErrorSeverity.MEDIUM, "ConnectionContext");
      return false;
    }
    
    if (!isAuthenticated) {
      AppErrorHandler.handleAuthError("Cannot reconnect: Please log in first", ErrorSeverity.MEDIUM, "ConnectionContext");
      return false;
    }
    
    logger.info("Attempting manual reconnection");
    
    try {
      return await connectionManagerRef.current.manualReconnect();
    } catch (error: any) {
      logger.error("Manual reconnect error", { error: error.message });
      return false;
    }
  }, [isAuthenticated, logger]);

  // Order action wrappers
  const submitOrder = React.useCallback(async (order: Parameters<ConnectionManager['submitOrder']>[0]) => {
    if (!connectionManagerRef.current) {
      logger.error("Submit order failed: ConnectionManager not initialized");
      return { success: false, error: "Connection service unavailable" };
    }
    
    if (!isAuthenticated) {
      logger.error("Submit order failed: User not authenticated");
      return { success: false, error: "User not authenticated" };
    }
    
    return connectionManagerRef.current.submitOrder(order);
  }, [isAuthenticated, logger]);

  const cancelOrder = React.useCallback(async (orderId: string) => {
    if (!connectionManagerRef.current) {
      logger.error("Cancel order failed: ConnectionManager not initialized");
      return { success: false, error: "Connection service unavailable" };
    }
    
    if (!isAuthenticated) {
      logger.error("Cancel order failed: User not authenticated");
      return { success: false, error: "User not authenticated" };
    }
    
    return connectionManagerRef.current.cancelOrder(orderId);
  }, [isAuthenticated, logger]);

  // Simulator action wrappers
  const startSimulator = React.useCallback(async () => {
    if (!connectionManagerRef.current) {
      logger.error("Start simulator failed: ConnectionManager not initialized");
      return { success: false, error: "Connection service unavailable" };
    }
    
    if (!isAuthenticated) {
      logger.error("Start simulator failed: User not authenticated");
      return { success: false, error: "User not authenticated" };
    }
    
    return connectionManagerRef.current.startSimulator();
  }, [isAuthenticated, logger]);

  const stopSimulator = React.useCallback(async () => {
    if (!connectionManagerRef.current) {
      logger.error("Stop simulator failed: ConnectionManager not initialized");
      return { success: false, error: "Connection service unavailable" };
    }
    
    if (!isAuthenticated) {
      logger.error("Stop simulator failed: User not authenticated");
      return { success: false, error: "User not authenticated" };
    }
    
    return connectionManagerRef.current.stopSimulator();
  }, [isAuthenticated, logger]);

  // Create context value with only actions (not state)
  const contextValue = React.useMemo<ConnectionContextType>(() => ({
    setDesiredState,
    manualReconnect,
    submitOrder,
    cancelOrder,
    startSimulator,
    stopSimulator,
  }), [
    setDesiredState,
    manualReconnect,
    submitOrder,
    cancelOrder,
    startSimulator,
    stopSimulator
  ]);

  return (
    <ConnectionContext.Provider value={contextValue}>
      {children}
    </ConnectionContext.Provider>
  );
};

// Custom hook to access connection actions from context
export const useConnectionActions = (): ConnectionContextType => {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error('useConnectionActions must be used within a ConnectionProvider');
  }
  return context;
};

// New hook for accessing connection state
export const useConnectionState = () => {
  return useAppState(state => state.connection);
};