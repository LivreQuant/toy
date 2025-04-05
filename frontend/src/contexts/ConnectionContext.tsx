// src/contexts/ConnectionContext.tsx

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  useCallback, // Added useCallback
  ReactNode,
} from 'react';
import { ConnectionManager } from '../services/connection/connection-manager';
import { TokenManager } from '../services/auth/token-manager'; // Adjust import path
import { Logger } from '../utils/logger'; // Adjust import path
import {
  ConnectionStatus,
  ConnectionQuality,
  ServiceState,
  UnifiedConnectionState // Import base class if needed for types
} from '../services/connection/unified-connection-state'; // Adjust import path
import { toastService } from '../services/notification/toast-service'; // Import toastService

// --- Define the type for the full connection state ---
// This gets the return type of the connectionManager.getState() method
export type FullConnectionState = ReturnType<ConnectionManager['getState']>;

// --- Define the type for the context value ---
// This includes the specific state properties and action methods needed by components
export interface ConnectionContextType {
  // State Properties (derived from FullConnectionState)
  isConnected: boolean;
  isConnecting: boolean;
  isRecovering: boolean;
  recoveryAttempt: number;
  connectionQuality: ConnectionQuality;
  simulatorStatus: string;
  webSocketState: ServiceState;
  sseState: ServiceState;
  overallStatus: ConnectionStatus; // Expose the overall status enum value
  // Add any other state properties components need directly

  // Action Methods (bound from ConnectionManager)
  connect: () => Promise<boolean>;
  disconnect: (reason?: string) => void;
  manualReconnect: () => Promise<boolean>;
  startSimulator: (options?: any) => Promise<{ success: boolean; status?: string; error?: string }>;
  stopSimulator: () => Promise<{ success: boolean; error?: string }>;
  // Add other methods components need (e.g., submitOrder, cancelOrder if managed here)
}

// --- Create Context ---
// Provide a default value that matches the type structure, often null or a placeholder
const defaultContextValue: ConnectionContextType | null = null;
const ConnectionContext = createContext<ConnectionContextType | null>(defaultContextValue);

// --- Define Provider Props ---
interface ConnectionProviderProps {
  children: ReactNode;
  tokenManager: TokenManager; // Pass dependencies needed by ConnectionManager
  logger: Logger;
}

// --- Create Provider Component ---
export const ConnectionProvider: React.FC<ConnectionProviderProps> = ({ children, tokenManager, logger }) => {
  // Instantiate ConnectionManager (only once)
  const connectionManager = useMemo(() => {
    logger.info("Instantiating ConnectionManager in Context Provider");
    // Ensure ConnectionManager constructor matches (tokenManager, logger, wsOptions, sseOptions)
    return new ConnectionManager(tokenManager, logger);
  }, [tokenManager, logger]); // Dependencies for ConnectionManager instantiation

  // State to hold the latest full connection state object
  const [connectionState, setConnectionState] = useState<FullConnectionState | null>(
    () => connectionManager.getState() // Get initial state synchronously
  );

  // Effect to subscribe to state changes
  useEffect(() => {
    logger.info("ConnectionProvider Effect: Subscribing to state changes");

    // Listener for state updates
    const handleStateChange = (newState: { current: FullConnectionState }) => {
      // logger.debug("ConnectionProvider: Received state_change event", newState.current); // Use debug if implemented
      logger.info("ConnectionProvider: Received state_change event", { status: newState.current.overallStatus });
      setConnectionState(newState.current);
    };

    // Subscribe
    connectionManager.on('state_change', handleStateChange);
    logger.info("ConnectionProvider: Subscribed to state_change");

    // Cleanup on unmount
    return () => {
      logger.warn("ConnectionProvider Cleanup: Unsubscribing and disposing ConnectionManager");
      connectionManager.off('state_change', handleStateChange);
      // Dispose the connection manager when the provider unmounts
      if (typeof connectionManager.dispose === 'function') {
        connectionManager.dispose();
      }
    };
  }, [connectionManager, logger]); // Dependency: only the manager instance

  // --- Define Action Callbacks using useCallback ---
  // This prevents these functions from causing unnecessary re-renders in consumers
  const connect = useCallback(async (): Promise<boolean> => {
      logger.info("Context: connect action triggered");
      return connectionManager.connect();
  }, [connectionManager, logger]); // Add logger if used inside

  const disconnect = useCallback((reason?: string): void => {
      logger.info(`Context: disconnect action triggered. Reason: ${reason}`);
      connectionManager.disconnect(reason);
  }, [connectionManager, logger]);

  const manualReconnect = useCallback(async (): Promise<boolean> => {
      logger.info("Context: manualReconnect action triggered");
      // Provide immediate feedback via toast
      toastService.info("Attempting to reconnect manually...");
      try {
          const success = await connectionManager.manualReconnect();
          if (success) {
              toastService.success("Reconnected successfully!");
          } else {
              // Error handling/toast is likely done within ConnectionManager/RecoveryManager now
              // toastService.error("Manual reconnect failed. Please check connection or try again later.");
          }
          return success;
      } catch (error: any) {
          logger.error("Context: Manual reconnect failed.", { error: error.message });
          toastService.error(`Manual reconnect failed: ${error.message}`);
          return false;
      }
  }, [connectionManager, logger]); // Add logger if used inside

  const startSimulator = useCallback(async (options?: any): Promise<{ success: boolean; status?: string; error?: string }> => {
      logger.info("Context: startSimulator action triggered");
      return connectionManager.startSimulator(options);
  }, [connectionManager, logger]);

  const stopSimulator = useCallback(async (): Promise<{ success: boolean; error?: string }> => {
      logger.info("Context: stopSimulator action triggered");
      return connectionManager.stopSimulator();
  }, [connectionManager, logger]);


  // --- Memoize the context value ---
  // This object is passed down and should only change when the state or callbacks change
  const contextValue = useMemo<ConnectionContextType | null>(() => {
    // Return null if state hasn't been initialized yet
    if (!connectionState) {
      logger.warn("ConnectionProvider: connectionState is null, returning null context value");
      return null;
    }

    logger.info("ConnectionProvider: Recalculating context value");
    // Derive the flat state properties needed by consumers from the full state object
    return {
      // State properties:
      isConnected: connectionState.isConnected,
      isConnecting: connectionState.isConnecting,
      isRecovering: connectionState.isRecovering,
      recoveryAttempt: connectionState.recoveryAttempt,
      connectionQuality: connectionState.connectionQuality,
      simulatorStatus: connectionState.simulatorStatus,
      webSocketState: connectionState.webSocketState,
      sseState: connectionState.sseState,
      overallStatus: connectionState.overallStatus,

      // Action methods:
      connect,
      disconnect,
      manualReconnect,
      startSimulator,
      stopSimulator,
    };
    // Dependencies ensure this only recalculates when state or action references change
  }, [connectionState, connect, disconnect, manualReconnect, startSimulator, stopSimulator, logger]); // Add logger if used inside

  return (
    <ConnectionContext.Provider value={contextValue}>
      {children}
    </ConnectionContext.Provider>
  );
};

// --- Custom Hook ---
// Provides a typed way to consume the context
export const useConnection = (): ConnectionContextType => {
  const context = useContext(ConnectionContext);
  if (context === null) {
    // This error means useConnection was called outside of a ConnectionProvider
    // or before the initial state was set.
    throw new Error('useConnection must be used within a ConnectionProvider and after initial state is set');
  }
  return context;
};
