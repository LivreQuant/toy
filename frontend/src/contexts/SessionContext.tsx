// src/contexts/SessionContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { ConnectionManager, ConnectionState } from '../services/session/connection-manager';
import { useAuth } from './AuthContext';
import { MarketData, OrderUpdate, PortfolioUpdate } from '../services/sse/market-data-stream';

interface SessionContextType {
  isConnected: boolean;
  isConnecting: boolean;
  sessionId: string | null;
  simulatorId: string | null;
  simulatorStatus: string;
  connectionQuality: 'good' | 'degraded' | 'poor';
  marketData: Record<string, MarketData>;
  orders: Record<string, OrderUpdate>;
  portfolio: PortfolioUpdate | null;
  connect: () => Promise<boolean>;
  disconnect: () => void;
  reconnect: () => Promise<boolean>;
  startSimulator: () => Promise<boolean>;
  stopSimulator: () => Promise<boolean>;
  submitOrder: (order: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price?: number;
    type: 'MARKET' | 'LIMIT';
  }) => Promise<{ success: boolean; orderId?: string; error?: string }>;
  cancelOrder: (orderId: string) => Promise<{ success: boolean; error?: string }>;
  error: string | null;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { tokenManager, isAuthenticated } = useAuth();
  
  // State
  const [connectionManager] = useState(() => new ConnectionManager(
    '/api',                   // REST API base URL
    'wss://api.yourdomain.com/ws',  // WebSocket URL (replace with your actual domain)
    '/api/v1/market-data',    // SSE URL
    tokenManager
  ));
  
  const [state, setState] = useState<ConnectionState>({
    isConnected: false,
    isConnecting: false,
    sessionId: null,
    simulatorId: null,
    simulatorStatus: 'UNKNOWN',
    connectionQuality: 'good',
    lastHeartbeatTime: 0,
    heartbeatLatency: null,
    podName: null,
    reconnectAttempt: 0,
    error: null
  });
  
  const [marketData, setMarketData] = useState<Record<string, MarketData>>({});
  const [orders, setOrders] = useState<Record<string, OrderUpdate>>({});
  const [portfolio, setPortfolio] = useState<PortfolioUpdate | null>(null);
  
  // Set up event listeners
  useEffect(() => {
    // Handle state changes
    connectionManager.on('state_change', ({ current }) => {
      setState(current);
    });
    
    // Handle market data updates
    connectionManager.on('market_data', (data) => {
      setMarketData(data);
    });
    
    // Handle order updates
    connectionManager.on('orders', (data) => {
      setOrders(data);
    });
    
    // Handle portfolio updates
    connectionManager.on('portfolio', (data) => {
      setPortfolio(data);
    });
    
    // Try to connect if authenticated
    if (isAuthenticated) {
      connectionManager.connect().catch(err => {
        console.error('Failed to connect on mount:', err);
      });
    }
    
    // Set up connection quality interval
    const qualityInterval = setInterval(() => {
      if (state.isConnected) {
        connectionManager.updateConnectionQuality().catch(err => {
          console.error('Failed to update connection quality:', err);
        });
      }
    }, 60000); // Once per minute
    
    // Clean up on unmount
    return () => {
      clearInterval(qualityInterval);
    };
  }, [connectionManager, isAuthenticated, state.isConnected]);
  
  // Connect, disconnect, and reconnect methods
  const connect = async (): Promise<boolean> => {
    return connectionManager.connect();
  };
  
  const disconnect = (): void => {
    connectionManager.disconnect();
  };
  
  const reconnect = async (): Promise<boolean> => {
    return connectionManager.reconnect();
  };
  
  // Simulator control methods
  const startSimulator = async (): Promise<boolean> => {
    return connectionManager.startSimulator();
  };
  
  const stopSimulator = async (): Promise<boolean> => {
    return connectionManager.stopSimulator();
  };
  
  // Order methods
  const submitOrder = async (order: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price?: number;
    type: 'MARKET' | 'LIMIT';
  }): Promise<{ success: boolean; orderId?: string; error?: string }> => {
    return connectionManager.submitOrder(order);
  };
  
  const cancelOrder = async (orderId: string): Promise<{ success: boolean; error?: string }> => {
    return connectionManager.cancelOrder(orderId);
  };
  
  return (
    <SessionContext.Provider
      value={{
        isConnected: state.isConnected,
        isConnecting: state.isConnecting,
        sessionId: state.sessionId,
        simulatorId: state.simulatorId,
        simulatorStatus: state.simulatorStatus,
        connectionQuality: state.connectionQuality,
        marketData,
        orders,
        portfolio,
        connect,
        disconnect,
        reconnect,
        startSimulator,
        stopSimulator,
        submitOrder,
        cancelOrder,
        error: state.error
      }}
    >
      {children}
    </SessionContext.Provider>
  );
};

export const useSession = (): SessionContextType => {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};