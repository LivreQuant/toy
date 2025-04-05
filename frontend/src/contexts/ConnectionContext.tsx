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
import { ConnectionManager } from '../services/connection/connection-manager';
import { TokenManager } from '../services/auth/token-manager';
import { Logger } from '../utils/logger';
import {
  ConnectionStatus,
  ConnectionQuality,
  ServiceState,
} from '../services/connection/unified-connection-state';
import { toastService } from '../services/notification/toast-service';
import { useAuth } from './AuthContext';

export type FullConnectionState = ReturnType<ConnectionManager['getState']>;

export interface ConnectionContextType {
  isConnected: boolean;
  isConnecting: boolean;
  isRecovering: boolean;
  recoveryAttempt: number;
  connectionQuality: ConnectionQuality;
  simulatorStatus: string;
  webSocketState: ServiceState;
  sseState: ServiceState;
  overallStatus: ConnectionStatus;
  lastHeartbeatTime?: number;
  heartbeatLatency?: number | null;
  disconnect: (reason?: string) => void;
  manualReconnect: () => Promise<boolean>;
  startSimulator: () => Promise<{ success: boolean; status?: string; error?: string }>;
  stopSimulator: () => Promise<{ success: boolean; error?: string }>;
}

// Default state representing a disconnected system
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
  sseState: {
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
  disconnect: () => {},
  manualReconnect: async () => false,
  startSimulator: async () => ({ success: false, error: "Not initialized" }),
  stopSimulator: async () => ({ success: false, error: "Not initialized" }),
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
  const isAuthenticatedRef = useRef(false);
  
  // Effect that runs when authentication status changes
  useEffect(() => {
    logger.info(`Auth status changed: isAuthenticated=${isAuthenticated}, isLoading=${isAuthLoading}`);
    
    // Keep track of last auth state for comparison
    isAuthenticatedRef.current = isAuthenticated;
    
    // Don't do anything while auth is still loading
    if (isAuthLoading) {
      logger.info("Auth still loading, waiting...");
      return;
    }
    
    // CASE 1: User is authenticated - initialize connection if needed
    if (isAuthenticated) {
      logger.info("User is authenticated, initializing connection services");
      
      // Only create a new ConnectionManager if one doesn't exist
      if (!connectionManagerRef.current) {
        logger.info("Creating new ConnectionManager instance");
        
        // Create the ConnectionManager
        const newConnectionManager = new ConnectionManager(tokenManager, logger);
        connectionManagerRef.current = newConnectionManager;
        
        // Set up state change listener
        newConnectionManager.on('state_change', (data: { current: FullConnectionState }) => {
          logger.info(`Connection state changed: ${data.current.overallStatus}`);
          setConnectionState(data.current);
        });
        
        // Initiate connection after a short delay to ensure everything is ready
        const connectionTimer = setTimeout(() => {
          if (connectionManagerRef.current && isAuthenticatedRef.current) {
            logger.info("Initiating connection after authentication");
            connectionManagerRef.current.connect().catch(err => {
              logger.error("Initial connection attempt failed", { error: err.message });
            });
          }
        }, 500); // Small delay to ensure auth state is stable
        
        // Cleanup function to clear timer if component unmounts quickly
        return () => {
          clearTimeout(connectionTimer);
        };
      }
      
      // If ConnectionManager already exists, no need to recreate it
      return;
    }
    
    // CASE 2: User is not authenticated - clean up connection services
    logger.info("User is not authenticated, cleaning up connection services");
    
    if (connectionManagerRef.current) {
      // Clean up the existing ConnectionManager
      logger.warn("Disposing existing ConnectionManager due to auth change");
      const manager = connectionManagerRef.current;
      
      // Disconnect and dispose
      manager.disconnect('auth_change');
      manager.dispose();
      connectionManagerRef.current = null;
      
      // Reset to default state
      setConnectionState(defaultState as FullConnectionState);
    }
  }, [isAuthenticated, isAuthLoading, tokenManager, logger]);
  
  // Effect to cleanup on unmount
  useEffect(() => {
    return () => {
      // Cleanup on unmount
      if (connectionManagerRef.current) {
        logger.warn("Cleaning up ConnectionManager on unmount");
        connectionManagerRef.current.disconnect('component_unmount');
        connectionManagerRef.current.dispose();
        connectionManagerRef.current = null;
      }
    };
  }, [logger]);

  // Define action callbacks
  const disconnect = useCallback((reason?: string): void => {
    if (connectionManagerRef.current) {
      logger.info(`Disconnect requested. Reason: ${reason}`);
      connectionManagerRef.current.disconnect(reason);
    } else {
      logger.warn("Disconnect called but ConnectionManager not initialized");
    }
  }, [logger]);

  const manualReconnect = useCallback(async (): Promise<boolean> => {
    if (!connectionManagerRef.current) {
      logger.error("Manual reconnect failed: ConnectionManager not initialized");
      toastService.error("Connection service unavailable");
      return false;
    }
    
    if (!isAuthenticated) {
      toastService.error("Cannot reconnect: Please log in first");
      return false;
    }
    
    toastService.info("Attempting to reconnect...");
    try {
      return await connectionManagerRef.current.manualReconnect();
    } catch (error: any) {
      logger.error("Manual reconnect failed", { error: error.message });
      return false;
    }
  }, [isAuthenticated, logger]);

  const startSimulator = useCallback(async (): Promise<{ success: boolean; status?: string; error?: string }> => {
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

  const stopSimulator = useCallback(async (): Promise<{ success: boolean; error?: string }> => {
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

  // Combine connection state with action methods
  const contextValue = useMemo<ConnectionContextType>(() => ({
    ...connectionState,
    disconnect,
    manualReconnect,
    startSimulator,
    stopSimulator,
  }), [
    connectionState, 
    disconnect, 
    manualReconnect, 
    startSimulator, 
    stopSimulator
  ]);

  return (
    <ConnectionContext.Provider value={contextValue}>
      {children}
    </ConnectionContext.Provider>
  );
};

// Custom hook to use the connection context
export const useConnection = (): ConnectionContextType => {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error('useConnection must be used within a ConnectionProvider');
  }
  return context;
};