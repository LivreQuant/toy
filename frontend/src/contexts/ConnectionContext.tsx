// src/contexts/ConnectionContext.tsx (Corrected Imports)
import React, { createContext, ReactNode, useMemo, useEffect, useState, useContext } from 'react';
import { ConnectionManager } from '../services/connection/connection-manager';
// Import AppState type, appState instance, AND necessary Enums/initial state structure
import { appState, AppState, ConnectionStatus, ConnectionQuality, initialState } from '../services/state/app-state.service';
import { Observable, Subscription } from 'rxjs';
import { getLogger } from '../boot/logging';
import LoadingSpinner from '../components/Common/LoadingSpinner';

// ... (Keep ConnectionContextProps interface) ...
interface ConnectionContextProps {
  connectionManager: ConnectionManager;
  connectionState: AppState['connection']; // Correct type
  isConnected: boolean;
  isConnecting: boolean;
  isRecovering: boolean;
}

export const ConnectionContext = createContext<ConnectionContextProps | undefined>(undefined);

// ... (Keep ConnectionProviderProps interface) ...
interface ConnectionProviderProps {
  children: ReactNode;
  connectionManager: ConnectionManager;
}

const logger = getLogger('ConnectionContext');

export const ConnectionProvider: React.FC<ConnectionProviderProps> = ({ children, connectionManager }) => {
  const [connectionState, setConnectionState] = useState<AppState['connection'] | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    logger.info('ConnectionProvider mounting, subscribing to AppState connection changes.');
    const stateSubscription: Subscription = appState.getConnectionState$()
      .subscribe({ next: (connState) => { /* ... */ }, error: (err) => { /* ... */ } }); // Corrected subscribe
    return () => { /* ... unsubscribe ... */ };
  }, [connectionManager]);

  const contextValue = useMemo(() => {
     // Use imported initialState structure as default
     const currentConnState = connectionState ?? initialState.connection;
     // Use imported enum
     const isConnected = currentConnState.overallStatus === ConnectionStatus.CONNECTED;
     const isConnecting = currentConnState.overallStatus === ConnectionStatus.CONNECTING || currentConnState.overallStatus === ConnectionStatus.RECOVERING;
     const isRecovering = currentConnState.isRecovering;
     // ... (rest of useMemo remains the same) ...
     return { connectionManager, connectionState: currentConnState, isConnected, isConnecting, isRecovering };
  }, [connectionManager, connectionState]);

  if (isLoading && !connectionState) { // Check connectionState presence as well
     return <LoadingSpinner message="Initializing connection state..." />;
  }

  return (
    <ConnectionContext.Provider value={contextValue}>
      {children}
    </ConnectionContext.Provider>
  );
};

// ... (Keep useConnection hook) ...
export const useConnection = () => {
  const context = useContext(ConnectionContext);
  if (context === undefined) {
    throw new Error('useConnection must be used within a ConnectionProvider');
  }
  return context;
};