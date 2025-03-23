// src/contexts/MarketDataContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { useSession } from './SessionContext';
import { MarketData, OrderUpdate, PortfolioUpdate } from '../services/sse/market-data-stream';

interface MarketDataContextProps {
  marketData: Record<string, MarketData>;
  orders: Record<string, OrderUpdate>;
  portfolio: PortfolioUpdate | null;
  isLoading: boolean;
  error: string | null;
  selectedSymbol: string | null;
  setSelectedSymbol: (symbol: string | null) => void;
}

const MarketDataContext = createContext<MarketDataContextProps | undefined>(undefined);

export const MarketDataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isConnected, marketData, orders, portfolio } = useSession();
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  
  // Update loading state based on connection and data
  useEffect(() => {
    if (!isConnected) {
      setIsLoading(true);
      return;
    }
    
    // If we have market data, we're no longer loading
    if (Object.keys(marketData).length > 0) {
      setIsLoading(false);
    }
    
    // Check for selected symbol validity
    if (selectedSymbol && !marketData[selectedSymbol]) {
      // If the selected symbol is no longer in the data, select the first available one
      const symbols = Object.keys(marketData);
      if (symbols.length > 0) {
        setSelectedSymbol(symbols[0]);
      } else {
        setSelectedSymbol(null);
      }
    }
  }, [isConnected, marketData, selectedSymbol]);
  
  return (
    <MarketDataContext.Provider
      value={{
        marketData,
        orders,
        portfolio,
        isLoading,
        error,
        selectedSymbol,
        setSelectedSymbol
      }}
    >
      {children}
    </MarketDataContext.Provider>
  );
};

export const useMarketData = (): MarketDataContextProps => {
  const context = useContext(MarketDataContext);
  if (context === undefined) {
    throw new Error('useMarketData must be used within a MarketDataProvider');
  }
  return context;
};