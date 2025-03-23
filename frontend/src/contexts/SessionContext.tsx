// src/contexts/SessionContext.tsx
import React, { createContext, useContext } from 'react';
import { useConnection } from './ConnectionContext';

interface SessionContextProps {
  sessionId: string | null;
  simulatorId: string | null;
  simulatorStatus: string;
  isConnected: boolean;
  marketData: Record<string, any>;
  orders: Record<string, any>;
  portfolio: any;
  startSimulator: () => Promise<boolean>;
  stopSimulator: () => Promise<boolean>;
  submitOrder: (order: any) => Promise<any>;
  streamMarketData: (symbols: string[]) => Promise<boolean>;
}

const SessionContext = createContext<SessionContextProps | undefined>(undefined);

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { connectionManager, connectionState, isConnected } = useConnection();
  
  // Extract what we need from connection state
  const { sessionId, simulatorId, simulatorStatus } = connectionState;
  
  // Get market data from connection manager
  const marketData = React.useMemo(() => connectionManager.getMarketData(), [connectionManager]);
  const orders = React.useMemo(() => connectionManager.getOrders(), [connectionManager]);
  const portfolio = React.useMemo(() => connectionManager.getPortfolio(), [connectionManager]);
  
  // React to market data updates
  React.useEffect(() => {
    const handleMarketData = () => {
      // This will cause a re-render with new data
      forceUpdate();
    };
    
    connectionManager.on('market_data', handleMarketData);
    connectionManager.on('orders', handleMarketData);
    connectionManager.on('portfolio', handleMarketData);
    
    return () => {
      connectionManager.off('market_data', handleMarketData);
      connectionManager.off('orders', handleMarketData);
      connectionManager.off('portfolio', handleMarketData);
    };
  }, [connectionManager]);
  
  // Force update function (simplified for this example)
  const [, setCounter] = React.useState(0);
  const forceUpdate = () => setCounter(c => c + 1);
  
  // Stream market data for specific symbols
  const streamMarketData = async (symbols: string[]) => {
    return connectionManager.streamMarketData(symbols);
  };
  
  // Provide simpler wrapper methods
  const startSimulator = async () => {
    return connectionManager.startSimulator();
  };
  
  const stopSimulator = async () => {
    return connectionManager.stopSimulator();
  };
  
  // Placeholder for order submission - would integrate with order service
  const submitOrder = async (order: any) => {
    // Implementation would depend on your order API
    return { success: true };
  };
  
  return (
    <SessionContext.Provider value={{
      sessionId,
      simulatorId,
      simulatorStatus,
      isConnected,
      marketData,
      orders,
      portfolio,
      startSimulator,
      stopSimulator,
      submitOrder,
      streamMarketData
    }}>
      {children}
    </SessionContext.Provider>
  );
};

export const useSession = (): SessionContextProps => {
  const context = useContext(SessionContext);
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return context;
};