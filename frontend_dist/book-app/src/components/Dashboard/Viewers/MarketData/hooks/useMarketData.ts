// src/components/Dashboard/Viewers/MarketData/hooks/useMarketData.ts
import { useState, useRef, useEffect } from 'react';
import { useConnection } from '../../../../../hooks/useConnection';
import { ColumnStateService } from '../../../AgGrid/services/columnStateService';
import { ExchangeDataStore } from '../../../../../stores/ExchangeDataStore';
import { EquityDataItem } from '../../../../../types/ExchangeData';

export enum MarketDataStatus {
  READY = 'READY',
  LOADING = 'LOADING',
  ERROR = 'ERROR',
  NO_DATA = 'NO_DATA'
}

// Transform equity data to match existing MarketDataBar interface
export interface MarketDataBar {
  instrument: string;
  exchange: string;
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  change?: number;
  priceDirection?: number;
}

function transformEquityToMarketData(equity: EquityDataItem): MarketDataBar {
  return {
    instrument: equity.symbol,
    exchange: equity.exchange_type,
    timestamp: Date.now(), // Use current time since equity data doesn't have individual timestamps
    open: equity.open,
    high: equity.high,
    low: equity.low,
    close: equity.close,
    volume: equity.volume,
    change: undefined, // Calculate if needed
    priceDirection: undefined // Calculate if needed
  };
}

export const useMarketData = (viewId: string) => {
  const [marketData, setMarketData] = useState<MarketDataBar[]>([]);
  const [status, setStatus] = useState<MarketDataStatus>(MarketDataStatus.NO_DATA);
  const [error, setError] = useState<string | null>(null);
  const [dataCount, setDataCount] = useState<number>(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  
  const { connectionManager, isConnected } = useConnection();
  const latestDataRef = useRef<MarketDataBar[]>([]);
  const store = ExchangeDataStore.getInstance();

  // Process and transform market data with proper column order
  const processMarketDataWithColumnOrder = (data: MarketDataBar[]) => {
    const columnStateService = ColumnStateService.getInstance();
    const savedColumnOrder = columnStateService.getOrderedColumns(viewId);
    
    if (!savedColumnOrder || savedColumnOrder.length === 0) {
      return data;
    }
    
    return data.map(bar => {
      const orderedBar: {[key: string]: any} = {};
      
      savedColumnOrder.forEach(colId => {
        if (bar.hasOwnProperty(colId)) {
          orderedBar[colId] = (bar as any)[colId];
        }
      });
      
      return {
        ...bar,
        ...orderedBar
      };
    });
  };

  // Handle equity data updates from the store
  useEffect(() => {
    if (!isConnected) {
      setStatus(MarketDataStatus.NO_DATA);
      setError('Not connected to data stream');
      return;
    }

    setStatus(MarketDataStatus.LOADING);
    setError(null);

    // Subscribe to equity data updates
    const subscription = store.getEquityData$().subscribe({
      next: (equityData: EquityDataItem[]) => {
        if (equityData && equityData.length > 0) {
          // Transform equity data to market data format
          const transformedData = equityData.map(transformEquityToMarketData);
          const processedData = processMarketDataWithColumnOrder(transformedData);
          
          setMarketData(processedData);
          latestDataRef.current = processedData;
          setDataCount(processedData.length);
          setLastUpdated(new Date().toLocaleTimeString());
          setStatus(MarketDataStatus.READY);
        } else {
          setMarketData([]);
          latestDataRef.current = [];
          setDataCount(0);
          setStatus(MarketDataStatus.NO_DATA);
        }
      },
      error: (err) => {
        console.error('Market Data Stream Error:', err);
        setError(err.message);
        setStatus(MarketDataStatus.ERROR);
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [isConnected, viewId]);

  // Subscribe to last update timestamp for UI refresh
  useEffect(() => {
    const subscription = store.getLastUpdate$().subscribe({
      next: (timestamp) => {
        if (timestamp > 0) {
          setLastUpdated(new Date(timestamp).toLocaleTimeString());
        }
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const clearData = () => {
    store.reset();
    setError(null);
    setStatus(MarketDataStatus.NO_DATA);
  };
  
  return {
    marketData,
    status,
    error,
    dataCount,
    lastUpdated,
    clearData,
  };
};