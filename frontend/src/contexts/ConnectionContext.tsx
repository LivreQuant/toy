
// src/contexts/ConnectionContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { ConnectionManager, ConnectionState } from '../services/connection/connection-manager';
import { TokenManager } from '../services/auth/token-manager';
import { useAuth } from './AuthContext';

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
  startSimulator: () => Promise<boolean>;
  stopSimulator: () => Promise<boolean>;
  submitOrder: (order: any) => Promise<any>;
  marketData: Record<string, any>;
  orders: Record<string, any>;
  portfolio: any;
  streamMarketData: (symbols: string[]) => Promise<boolean>;
}

const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

export const ConnectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { tokenManager, isAuthenticated } = useAuth();
  const [connectionManager] = useState<ConnectionManager>(() => 
    new ConnectionManager(
      '/api',                             // REST API endpoint
      `wss://${window.location.host}/ws`, // WebSocket endpoint
      '/api/stream/market-data',          // SSE endpoint
      tokenManager
    )
  );
  
  const [connectionState, setConnectionState] = useState<ConnectionState>(connectionManager.getState());
  const [marketData, setMarketData] = useState<Record<string, any>>({});
  const [orders, setOrders] = useState<Record<string, any>>({});
  const [portfolio, setPortfolio] = useState<any>(null);
  
  useEffect(() => {
    // Handle connection state changes
    const handleStateChange = ({ current }: { current: ConnectionState }) => {
      setConnectionState(current);
    };
    
    const handleMarketData = (data: any) => {
      setMarketData(data);
    };
    
    const handleOrders = (data: any) => {
      setOrders(data);
    };
    
    const handlePortfolio = (data: any) => {
      setPortfolio(data);
    };
    
    connectionManager.on('state_change', handleStateChange);
    connectionManager.on('market_data', handleMarketData);
    connectionManager.on('orders', handleOrders);
    connectionManager.on('portfolio', handlePortfolio);
    
    // Connect if authenticated
    if (isAuthenticated) {
      connectionManager.connect().catch(err => {
        console.error('Failed to connect on mount:', err);
      });
    }
    
    return () => {
      connectionManager.off('state_change', handleStateChange);
      connectionManager.off('market_data', handleMarketData);
      connectionManager.off('orders', handleOrders);
      connectionManager.off('portfolio', handlePortfolio);
      // Don't disconnect on unmount as this is a top-level provider
    };
  }, [connectionManager, isAuthenticated]);
  
  const connect = async () => {
    return connectionManager.connect();
  };
  
  const disconnect = () => {
    connectionManager.disconnect();
  };
  
  const reconnect = async () => {
    return connectionManager.reconnect();
  };

  const startSimulator = async () => {
    return connectionManager.startSimulator();
  };
  
  const stopSimulator = async () => {
    return connectionManager.stopSimulator();
  };
  
  const submitOrder = async (order: any) => {
    return connectionManager.submitOrder(order);
  };
  
  const streamMarketData = async (symbols: string[]) => {
    return connectionManager.streamMarketData(symbols);
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
      error: connectionState.error,
      startSimulator,
      stopSimulator,
      submitOrder,
      marketData,
      orders,
      portfolio,
      streamMarketData
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