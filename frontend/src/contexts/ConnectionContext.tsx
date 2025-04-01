// src/contexts/ConnectionContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { ConnectionManager, ConnectionState } from '../services/connection/connection-manager';
import { TokenManager } from '../services/auth/token-manager';
import { useAuth } from './AuthContext';
import { config } from '../config';

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
    new ConnectionManager(tokenManager)
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
      console.log('Connection Context - Received Market Data:', data);
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
    
    // Connection management based on authentication state
     if (isAuthenticated && !connectionState.isConnected && !connectionState.isConnecting) {
      // Connect automatically when authenticated and not already connected/connecting
      connectionManager.connect().catch(err => {
        console.error('Failed to auto-connect after authentication:', err);
      });
    } else if (!isAuthenticated && (connectionState.isConnected || connectionState.isConnecting)) {
      // Disconnect when authentication is lost
      connectionManager.disconnect();
    }
    
    return () => {
      connectionManager.off('state_change', handleStateChange);
      connectionManager.off('market_data', handleMarketData);
      connectionManager.off('orders', handleOrders);
      connectionManager.off('portfolio', handlePortfolio);
      // Don't disconnect on unmount as this is a top-level provider
    };
  }, [connectionManager, isAuthenticated, connectionState.isConnected, connectionState.isConnecting]);
  
  
  const connect = async () => {
    if (!isAuthenticated) {
      console.warn('Cannot connect - user is not authenticated');
      return false;
    }
    return connectionManager.connect();
  };
  
  const disconnect = () => {
    connectionManager.disconnect();
  };
  
  const reconnect = async () => {
    if (!isAuthenticated) {
      console.warn('Cannot reconnect - user is not authenticated');
      return false;
    }
    return connectionManager.reconnect();
  };

  const startSimulator = async () => {
    if (!isAuthenticated || !connectionState.isConnected) {
      console.warn('Cannot start simulator - user is not authenticated or not connected');
      return false;
    }
    return connectionManager.startSimulator();
  };
  
  const stopSimulator = async () => {
    if (!isAuthenticated || !connectionState.isConnected) {
      console.warn('Cannot stop simulator - user is not authenticated or not connected');
      return false;
    }
    return connectionManager.stopSimulator();
  };
  
  const submitOrder = async (order: any) => {
    if (!isAuthenticated || !connectionState.isConnected) {
      return { success: false, error: 'Not authenticated or connected' };
    }
    return connectionManager.submitOrder(order);
  };
  
  const streamMarketData = async (symbols: string[]) => {
    if (!isAuthenticated || !connectionState.isConnected) {
      console.warn('Cannot stream market data - user is not authenticated or not connected');
      return false;
    }
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