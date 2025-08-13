// src/hooks/usePortfolioData.ts
import { useState, useEffect } from 'react';
import { ExchangeDataStore } from '../stores/ExchangeDataStore';
import { PortfolioData, PositionDataItem } from '../types/ExchangeData';
import { useConnection } from './useConnection';

export const usePortfolioData = () => {
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [positions, setPositions] = useState<PositionDataItem[]>([]);
  const [totalValue, setTotalValue] = useState<number>(0);
  const [cashBalance, setCashBalance] = useState<number>(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const { isConnected } = useConnection();
  const store = ExchangeDataStore.getInstance();

  useEffect(() => {
    if (!isConnected) {
      setPortfolio(null);
      setPositions([]);
      setTotalValue(0);
      setCashBalance(0);
      setError('Not connected to data stream');
      return;
    }

    setError(null);

    // Subscribe to portfolio updates
    const subscription = store.getPortfolio$().subscribe({
      next: (portfolioData: PortfolioData | null) => {
        setPortfolio(portfolioData);
        
        if (portfolioData) {
          setPositions(portfolioData.positions);
          setTotalValue(portfolioData.total_value);
          setCashBalance(portfolioData.cash_balance);
          setLastUpdated(new Date().toLocaleTimeString());
        } else {
          setPositions([]);
          setTotalValue(0);
          setCashBalance(0);
        }
      },
      error: (err) => {
        console.error('Portfolio Data Stream Error:', err);
        setError(err.message);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [isConnected]);

  const clearData = () => {
    store.reset();
    setError(null);
  };

  return {
    portfolio,
    positions,
    totalValue,
    cashBalance,
    lastUpdated,
    error,
    clearData,
  };
};