// src/contexts/ConnectionContext.tsx

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  useCallback,
  ReactNode,
} from 'react';
import { ConnectionManager } from '../services/connection/connection-manager';
import { TokenManager } from '../services/auth/token-manager';
import { Logger } from '../utils/logger';
import {
  ConnectionStatus,
  ConnectionQuality,
  ServiceState,
  UnifiedConnectionState
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
  disconnect: (reason?: string) => void;
  manualReconnect: () => Promise<boolean>;
  startSimulator: () => Promise<{ success: boolean; status?: string; error?: string }>;
  stopSimulator: () => Promise<{ success: boolean; error?: string }>;
}

const defaultContextValue: ConnectionContextType | null = null;
const ConnectionContext = createContext<ConnectionContextType | null>(defaultContextValue);

interface ConnectionProviderProps {
  children: ReactNode;
  tokenManager: TokenManager;
  logger: Logger;
}

export const ConnectionProvider: React.FC<ConnectionProviderProps> = ({ children, tokenManager, logger }) => {
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();

  const connectionManager = useMemo(() => {
    logger.info("Instantiating ConnectionManager in Context Provider");
    return new ConnectionManager(tokenManager, logger);
  }, [tokenManager, logger]);

  const [connectionState, setConnectionState] = useState<FullConnectionState | null>(
    () => connectionManager.getState()
  );

  // Effect to subscribe to state changes from ConnectionManager
  useEffect(() => {
    logger.info("ConnectionProvider Effect: Subscribing to state changes");
    const handleStateChange = (newState: { current: FullConnectionState }) => {
      // Ensure we don't update state after disposal in Strict Mode's first run
      // Although CM checks internally, this adds safety here.
      if (connectionManager && !(connectionManager as any).isDisposed) {
         logger.info("ConnectionProvider: Received state_change", { status: newState.current.overallStatus });
         setConnectionState(newState.current);
      } else {
         logger.warn("ConnectionProvider: Received state_change but CM disposed/missing. Ignoring.");
      }
    };
    connectionManager.on('state_change', handleStateChange);
    logger.info("ConnectionProvider: Subscribed to state_change");

    // Cleanup
    let disposedManager = connectionManager; // Capture instance for cleanup
    return () => {
      logger.warn("ConnectionProvider Cleanup: Unsubscribing and disposing CM");
      disposedManager.off('state_change', handleStateChange);
      if (typeof disposedManager.dispose === 'function') {
        disposedManager.dispose();
      }
    };
  }, [connectionManager, logger]); // Re-run only if CM instance changes (shouldn't)

  // --- Effect to Connect/Disconnect based on Auth Status ---
  useEffect(() => {
    // Cannot proceed if the manager instance isn't available (e.g., during cleanup phase of Strict Mode)
     if (!connectionManager || (connectionManager as any).isDisposed) {
        logger.warn("ConnectionProvider Auth Effect: CM disposed/missing. Aborting.");
        return;
     }

    // Wait until the initial auth check is complete
    if (isAuthLoading) {
      logger.info("ConnectionProvider Auth Effect: Waiting for auth check...");
      return;
    }

    // Get current connection status *from the manager instance*
    const currentStatus = connectionManager.getState().overallStatus;

    if (isAuthenticated) {
      // Connect only if authenticated AND currently disconnected
      if (currentStatus === ConnectionStatus.DISCONNECTED) {
        logger.info("ConnectionProvider Auth Effect: Auth OK & Disconnected. Connecting...");
        connectionManager.connect().catch(err => {
            // Check disposed again after async operation completes
            if (connectionManager && !(connectionManager as any).isDisposed) {
                logger.error("ConnectionProvider Auth Effect: Initial connect call failed", { error: err });
            }
        });
      } else {
         logger.info("ConnectionProvider Auth Effect: Auth OK, but status not DISCONNECTED.", { currentStatus });
      }
    } else {
      // Disconnect only if !authenticated AND currently NOT disconnected
      // <<< ADDED CHECK: Only disconnect if not already disconnected >>>
      if (currentStatus !== ConnectionStatus.DISCONNECTED) {
         logger.warn("ConnectionProvider Auth Effect: Auth lost/out. Disconnecting...");
         // Pass specific reason
         connectionManager.disconnect('auth_state_false');
      } else {
          // Already disconnected, no need to call disconnect again
         logger.info("ConnectionProvider Auth Effect: Auth lost/out, already disconnected.");
      }
    }
  }, [isAuthenticated, isAuthLoading, connectionManager, logger]); // Dependencies

  // --- Action Callbacks ---
  // (disconnect, manualReconnect, startSimulator, stopSimulator - same as before, with auth checks)
   const disconnect = useCallback((reason?: string): void => {
       // Ensure manager exists before calling
      if (connectionManager && !(connectionManager as any).isDisposed) {
         logger.info(`Context: disconnect action. Reason: ${reason}`);
         connectionManager.disconnect(reason);
      } else {
         logger.warn("Context: disconnect action ignored, CM disposed/missing.");
      }
   }, [connectionManager, logger]);

  const manualReconnect = useCallback(async (): Promise<boolean> => {
    // Ensure manager exists
    if (!connectionManager || (connectionManager as any).isDisposed) {
        logger.error("Manual reconnect blocked: CM disposed/missing.");
        toastService.error("Connection service unavailable.");
        return false;
    }
    logger.info("Context: manualReconnect action");
    if (!isAuthenticated) {
        toastService.error("Cannot reconnect: Please log in first.");
        logger.error("Manual reconnect blocked: User not authenticated.");
        return false;
    }
    toastService.info("Attempting to reconnect manually...");
    try {
      const success = await connectionManager.manualReconnect();
      // Success/error toasts are likely handled internally now
      return success;
    } catch (error: any) {
      logger.error("Context: Manual reconnect failed.", { error: error.message });
      // Error handler might show toast, or add one here if needed
      // toastService.error(`Manual reconnect failed: ${error.message}`);
      return false;
    }
  }, [connectionManager, logger, isAuthenticated]);

  const startSimulator = useCallback(async (): Promise<{ success: boolean; status?: string; error?: string }> => {
     // Ensure manager exists
     if (!connectionManager || (connectionManager as any).isDisposed) {
        logger.error("Start simulator blocked: CM disposed/missing.");
        return { success: false, error: "Connection service unavailable." };
     }
     logger.info("Context: startSimulator action");
     if (!isAuthenticated) { /* ... auth check ... */ return { success: false, error: "User not authenticated" }; }
     return connectionManager.startSimulator();
   }, [connectionManager, logger, isAuthenticated]);

  const stopSimulator = useCallback(async (): Promise<{ success: boolean; error?: string }> => {
     // Ensure manager exists
     if (!connectionManager || (connectionManager as any).isDisposed) {
        logger.error("Stop simulator blocked: CM disposed/missing.");
        return { success: false, error: "Connection service unavailable." };
     }
     logger.info("Context: stopSimulator action");
      if (!isAuthenticated) { /* ... auth check ... */ return { success: false, error: "User not authenticated" }; }
     return connectionManager.stopSimulator();
   }, [connectionManager, logger, isAuthenticated]);

  // --- Memoize context value ---
  const contextValue = useMemo<ConnectionContextType | null>(() => {
    // If state is null (initial render or after disposal in Strict Mode), return null
    if (!connectionState) {
      // logger.warn("ConnectionProvider: connectionState is null, returning null context value");
      return null;
    }
    // logger.info("ConnectionProvider: Recalculating context value"); // Can be noisy
    return {
      isConnected: connectionState.isConnected,
      isConnecting: connectionState.isConnecting,
      isRecovering: connectionState.isRecovering,
      recoveryAttempt: connectionState.recoveryAttempt,
      connectionQuality: connectionState.connectionQuality,
      simulatorStatus: connectionState.simulatorStatus,
      webSocketState: connectionState.webSocketState,
      sseState: connectionState.sseState,
      overallStatus: connectionState.overallStatus,
      disconnect,
      manualReconnect,
      startSimulator,
      stopSimulator,
    };
  }, [connectionState, disconnect, manualReconnect, startSimulator, stopSimulator, logger]); // Added logger dependency

  return (
    <ConnectionContext.Provider value={contextValue}>
      {children}
    </ConnectionContext.Provider>
  );
};

// --- Custom Hook ---
export const useConnection = (): ConnectionContextType => {
  const context = useContext(ConnectionContext);
  if (context === null) {
    // This error means useConnection was called outside of ConnectionProvider
    // or potentially during the Strict Mode cleanup/remount phase before value is ready.
    // Components using this should ideally handle the loading state from useAuth.
    throw new Error('useConnection must be used within a ConnectionProvider and after initial state/auth is resolved');
  }
  return context;
};