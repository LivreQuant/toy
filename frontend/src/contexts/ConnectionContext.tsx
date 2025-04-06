// src/contexts/ConnectionContext.tsx
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  useCallback,
  ReactNode,
  useRef,
} from 'react';
import { ConnectionManager, ConnectionDesiredState } from '../services/connection/connection-manager';
import { TokenManager } from '../services/auth/token-manager';
import { Logger } from '../utils/logger';
import {
  ConnectionStatus,
  ConnectionQuality,
} from '../services/connection/unified-connection-state';
import { AppErrorHandler } from '../utils/app-error-handler';
import { useAuth } from './AuthContext';

export type FullConnectionState = ReturnType<ConnectionManager['getState']>;

export interface ConnectionContextType {
  // Connection State
  isConnected: boolean;
  isConnecting: boolean;
  isRecovering: boolean;
  recoveryAttempt: number;
  connectionQuality: ConnectionQuality;
  simulatorStatus: string;
  overallStatus: ConnectionStatus;
  lastHeartbeatTime?: number;
  heartbeatLatency?: number | null;
  
  // Connection Actions
  setDesiredState: (state: Partial<ConnectionDesiredState>) => void;
  manualReconnect: () => Promise<boolean>;
  
  // Order Actions
  submitOrder: ConnectionManager['submitOrder'];
  cancelOrder: ConnectionManager['cancelOrder'];
  
  // Simulator Actions
  startSimulator: ConnectionManager['startSimulator'];
  stopSimulator: ConnectionManager['stopSimulator'];
  
  // Data Access
  getExchangeData: ConnectionManager['getExchangeData'];
  getPortfolioData: ConnectionManager['getPortfolioData'];
  getRiskData: ConnectionManager['getRiskData'];
}

// Default state
const defaultState = {
  isConnected: false,
  isConnecting: false,
  isRecovering: false,
  recoveryAttempt: 0,
  connectionQuality: ConnectionQuality.UNKNOWN,
  simulatorStatus: 'UNKNOWN',
  webSocketState: {
    status: ConnectionStatus.DISCONNECTED,
    lastConnected: null,
    error: null,
    recoveryAttempts: 0
  },
  lastHeartbeatTime: 0,
  heartbeatLatency: null,
  overallStatus: ConnectionStatus.DISCONNECTED,
};

// Create context with default values
const ConnectionContext = createContext<ConnectionContextType>({
  ...defaultState,
  setDesiredState: () => {},
  manualReconnect: async () => false,
  submitOrder: async () => ({ success: false, error: "Not initialized" }),
  cancelOrder: async () => ({ success: false, error: "Not initialized" }),
  startSimulator: async () => ({ success: false, error: "Not initialized" }),
  stopSimulator: async () => ({ success: false, error: "Not initialized" }),
  getExchangeData: () => ({}),
  getPortfolioData: () => ({}),
  getRiskData: () => ({}),
});

interface ConnectionProviderProps {
  children: ReactNode;
  tokenManager: TokenManager;
  logger: Logger;
}

export const ConnectionProvider: React.FC<ConnectionProviderProps> = ({ 
  children, 
  tokenManager, 
  logger 
}) => {
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const [connectionState, setConnectionState] = useState<FullConnectionState>(defaultState as FullConnectionState);
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
        const newConnectionManager = new ConnectionManager(tokenManager, logger);
        connectionManagerRef.current = newConnectionManager;
        
        // Listen for state changes
        newConnectionManager.on('state_change', (data: { current: FullConnectionState }) => {
          logger.info(`Connection state changed: ${data.current.overallStatus}`);
          setConnectionState(data.current);
        });
        
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
        setConnectionState(defaultState as FullConnectionState);
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
  const setDesiredState = useCallback((state: Partial<ConnectionDesiredState>): void => {
    if (connectionManagerRef.current) {
      logger.info(`Setting desired state: ${JSON.stringify(state)}`);
      connectionManagerRef.current.setDesiredState(state);
    } else {
      logger.warn("setDesiredState called but ConnectionManager not initialized");
    }
  }, [logger]);

  const manualReconnect = useCallback(async (): Promise<boolean> => {
    if (!connectionManagerRef.current) {
      logger.error("Manual reconnect failed: ConnectionManager not initialized");
      AppErrorHandler.handleConnectionError("Connection service unavailable", undefined, "ConnectionContext");
      return false;
    }
    
    if (!isAuthenticated) {
      AppErrorHandler.handleAuthError("Cannot reconnect: Please log in first", undefined, "ConnectionContext");
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
  const submitOrder = useCallback(async (order: Parameters<ConnectionManager['submitOrder']>[0]) => {
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

  const cancelOrder = useCallback(async (orderId: string) => {
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
  const startSimulator = useCallback(async () => {
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

  const stopSimulator = useCallback(async () => {
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

  // Data accessor wrappers
  const getExchangeData = useCallback(() => {
    if (!connectionManagerRef.current) {
      logger.warn("getExchangeData called but ConnectionManager not initialized");
      return {};
    }
    return connectionManagerRef.current.getExchangeData();
  }, [logger]);

  const getPortfolioData = useCallback(() => {
    if (!connectionManagerRef.current) {
      logger.warn("getPortfolioData called but ConnectionManager not initialized");
      return {};
    }
    return connectionManagerRef.current.getPortfolioData();
  }, [logger]);

  const getRiskData = useCallback(() => {
    if (!connectionManagerRef.current) {
      logger.warn("getRiskData called but ConnectionManager not initialized");
      return {};
    }
    return connectionManagerRef.current.getRiskData();
  }, [logger]);

  // Create context value
  const contextValue = useMemo<ConnectionContextType>(() => ({
    ...connectionState,
    setDesiredState,
    manualReconnect,
    submitOrder,
    cancelOrder,
    startSimulator,
    stopSimulator,
    getExchangeData,
    getPortfolioData,
    getRiskData,
  }), [
    connectionState,
    setDesiredState,
    manualReconnect,
    submitOrder,
    cancelOrder,
    startSimulator,
    stopSimulator,
    getExchangeData,
    getPortfolioData,
    getRiskData
  ]);

  return (
    <ConnectionContext.Provider value={contextValue}>
      {children}
    </ConnectionContext.Provider>
  );
};

// Custom hook to access the connection context
export const useConnection = (): ConnectionContextType => {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error('useConnection must be used within a ConnectionProvider');
  }
  return context;
};