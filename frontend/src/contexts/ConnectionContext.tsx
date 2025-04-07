// src/contexts/ConnectionContext.tsx
import React, {
  createContext,
  ReactNode,
  useMemo,
  useEffect,
  useState,
  useContext,
} from 'react';
import { ConnectionManager } from '../services/connection/connection-manager';
// Fix the import to use the correct type
import {
  appState,
  ConnectionStatus,
  initialState as appInitialState,
} from '../services/state/app-state.service';
import { Subscription } from 'rxjs';
import { getLogger } from '../boot/logging';
import LoadingSpinner from '../components/Common/LoadingSpinner';
import { useAuth } from '../hooks/useAuth';

// Define the shape of your context data
interface ConnectionContextValue {
  connectionManager: ConnectionManager;
  connectionState: typeof appInitialState.connection;
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

  // Local state holds the connection slice from AppState
  const [connectionState, setConnectionState] = useState(
    () => appState.getState().connection
  );

  // Subscribe to Connection State Changes
  useEffect(() => {
    logger.info(
      'ConnectionProvider subscribing to AppState connection changes.'
    );
    const stateSubscription: Subscription = appState
      .select((s) => s.connection)
      .subscribe({
        next: (connState) => {
          setConnectionState(connState);
        },
        error: (err) => {
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
    const currentConnState = connectionState ?? appInitialState.connection;
    const isConnected =
      currentConnState.overallStatus === ConnectionStatus.CONNECTED;
    const isConnecting =
      currentConnState.overallStatus === ConnectionStatus.CONNECTING ||
      currentConnState.isRecovering;
    const isRecovering = currentConnState.isRecovering;

    return {
      connectionManager,
      connectionState: currentConnState,
      isConnected,
      isConnecting,
      isRecovering,
    };
  }, [connectionManager, connectionState]);

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