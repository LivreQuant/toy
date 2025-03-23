// src/contexts/ConnectionContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { ConnectionManager, ConnectionState } from '../services/connection/ConnectionManager';
import { TokenManager } from '../services/auth/token-manager';
import { useAuth } from './AuthContext';

// Initialize managers
const tokenManager = new TokenManager();
const connectionManager = new ConnectionManager(
  '/api',                                // REST API endpoint
  `wss://${window.location.host}/ws`,    // WebSocket endpoint
  '/api/stream/market-data',             // SSE endpoint
  tokenManager
);

interface ConnectionContextType {
  connectionManager: ConnectionManager;
  connectionState: ConnectionState;
  connect: () => Promise<boolean>;
  disconnect: () => void;
  reconnect: () => Promise<boolean>;
  isConnected: boolean;
  isConnecting: boolean;
  connectionQuality: string;
  error: string | null;
}

const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

export const ConnectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [connectionState, setConnectionState] = useState<ConnectionState>(connectionManager.getState());
  const { isAuthenticated } = useAuth();
  
  useEffect(() => {
    // Handle connection state changes
    const handleStateChange = ({ current }: { current: ConnectionState }) => {
      setConnectionState(current);
    };
    
    connectionManager.on('state_change', handleStateChange);
    
    // Connect if authenticated
    if (isAuthenticated) {
      connectionManager.connect().catch(err => {
        console.error('Failed to connect on mount:', err);
      });
    }
    
    return () => {
      connectionManager.off('state_change', handleStateChange);
      // Don't disconnect on unmount as this is a top-level provider
    };
  }, [isAuthenticated]);
  
  const connect = async () => {
    return connectionManager.connect();
  };
  
  const disconnect = () => {
    connectionManager.disconnect();
  };
  
  const reconnect = async () => {
    return connectionManager.reconnect();
  };
  
  return (
    <ConnectionContext.Provider value={{
      connectionManager,
      connectionState,
      connect,
      disconnect,
      reconnect,
      isConnected: connectionState.isConnected,
      isConnecting: connectionState.isConnecting,
      connectionQuality: connectionState.connectionQuality,
      error: connectionState.error
    }}>
      {children}
    </ConnectionContext.Provider>
  );
};

export const useConnection = (): ConnectionContextType => {
  const context = useContext(ConnectionContext);
  if (context === undefined) {
    throw new Error('useConnection must be used within a ConnectionProvider');
  }
  return context;
};