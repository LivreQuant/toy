// src/contexts/ConnectionContext.tsx
import React, {
  createContext,
  ReactNode,
  useMemo,
  useEffect,
  useState,
  useContext,
} from 'react';
import { Subscription } from 'rxjs';

import { getLogger } from '../boot/logging';

import { ConnectionManager } from '../services/connection/connection-manager';
import {
  connectionState as globalConnectionState,
  ConnectionStatus,
  ConnectionState,
  initialConnectionState
} from '../state/connection-state';

import { useAuth } from '../hooks/useAuth';

type ConnectionStateType = {
  overallStatus: ConnectionStatus;
  webSocketStatus: ConnectionStatus;
  quality: any; // Use the actual type from your code
  isRecovering: boolean;
  recoveryAttempt: number;
  heartbeatLatency?: number | null;
  simulatorStatus: string;
  lastConnectionError: string | null;
};

// Define the shape of your context data
interface ConnectionContextValue {
  connectionManager: ConnectionManager;
  connectionState: ConnectionStateType;
  isConnected: boolean;
  isConnecting: boolean;
  isRecovering: boolean;
}

// Create the context
export const ConnectionContext = createContext<ConnectionContextValue | undefined>(
  undefined
);

interface ConnectionProviderProps {
  children: ReactNode;
  connectionManager: ConnectionManager;
}

const logger = getLogger('ConnectionContext');

export const ConnectionProvider: React.FC<ConnectionProviderProps> = ({
  children,
  connectionManager,
}) => {
  // Use Auth State
  const { isAuthenticated, isAuthLoading } = useAuth();

  // Replace with explicit typing
  const [connectionState, setConnectionState] = useState<ConnectionState>(
    () => globalConnectionState.getState()
  );

  const [localConnectionState, setLocalConnectionState] = useState<ConnectionState>(
    () => globalConnectionState.getState()
  );
  
  // Subscribe to Connection State Changes
  useEffect(() => {
    logger.info(
      'ConnectionProvider subscribing to AppState connection changes.'
    );
    const stateSubscription: Subscription = globalConnectionState
      .getState$()
      .subscribe({
        next: (connState: ConnectionStateType) => {
          setLocalConnectionState(connState);
        },
        error: (err: any) => {
          logger.error('Error subscribing to connection state', { error: err });
        },
      });

    return () => {
      logger.info('ConnectionProvider unsubscribing from connection state.');
      stateSubscription.unsubscribe();
    };
  }, []);

  // Initialize ConnectionManager
  useEffect(() => {
    logger.info('ConnectionProvider initialized');
    
    return () => {
      logger.info('ConnectionProvider unmounting');
    };
  }, [connectionManager]);

  // Memoize the context value
  const contextValue = useMemo(() => {
    const currentConnState = connectionState ?? initialConnectionState;
    const isConnected =
      currentConnState.overallStatus === ConnectionStatus.CONNECTED;
    const isConnecting =
      currentConnState.overallStatus === ConnectionStatus.CONNECTING ||
      currentConnState.isRecovering;
    const isRecovering = currentConnState.isRecovering;

    console.log("CRITICAL DEBUG: ConnectionContext value calculation:", {
      overallStatus: currentConnState.overallStatus,
      webSocketStatus: currentConnState.webSocketStatus,
      isConnected,
      isConnecting,
      isRecovering
    });
    
    return {
      connectionManager,
      connectionState: localConnectionState,
      isConnected,
      isConnecting,
      isRecovering,
    };
  }, [connectionManager, localConnectionState]);

  // Conditional rendering
  if (isAuthLoading) {
    logger.debug('Auth is loading, rendering null');
    return null;
  }

  logger.debug('Auth resolved, rendering ConnectionContext.Provider');
  return (
    <ConnectionContext.Provider value={contextValue}>
      {children}
    </ConnectionContext.Provider>
  );
};

// Custom hook
export const useConnection = () => {
  const context = useContext(ConnectionContext);
  if (context === undefined) {
    throw new Error('useConnection must be used within a ConnectionProvider');
  }
  return context;
};