// frontend_dist/book-app/src/components/Dashboard/Viewers/MarketData/hooks/useMarketData.ts
import { useState, useRef, useEffect } from 'react';
import { useConnection } from '../../../../../contexts/ConnectionContext';
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
  console.log('🔍 useMarketData hook called for viewId:', viewId);
  
  const [marketData, setMarketData] = useState<MarketDataBar[]>([]);
  const [status, setStatus] = useState<MarketDataStatus>(MarketDataStatus.NO_DATA);
  const [error, setError] = useState<string | null>(null);
  const [dataCount, setDataCount] = useState<number>(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  
  const { connectionManager, isConnected } = useConnection();
  const latestDataRef = useRef<MarketDataBar[]>([]);
  const store = ExchangeDataStore.getInstance();

  console.log('🔍 useMarketData - isConnected:', isConnected);
  console.log('🔍 useMarketData - store:', store);
  console.log('🔍 useMarketData - connectionManager:', connectionManager);

  // Process and transform market data with proper column order
  const processMarketDataWithColumnOrder = (data: MarketDataBar[]) => {
    const columnStateService = ColumnStateService.getInstance();
    const savedColumnOrder = columnStateService.getOrderedColumns(viewId);
    
    if (!savedColumnOrder || savedColumnOrder.length === 0) {
      console.log('🔍 useMarketData - No saved column order, returning data as-is');
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
    console.log('🔍 useMarketData - Setting up subscription, isConnected:', isConnected);
    
    if (!isConnected) {
      setStatus(MarketDataStatus.NO_DATA);
      setError('Not connected to data stream');
      console.log('🔍 useMarketData - Not connected, returning early');
      return;
    }

    setStatus(MarketDataStatus.LOADING);
    setError(null);
    console.log('🔍 useMarketData - About to subscribe to store.getEquityData$()');

    // Subscribe to equity data updates
    const subscription = store.getEquityData$().subscribe({
      next: (equityData: EquityDataItem[]) => {
        console.log('🔍 useMarketData - Received equity data from store:', {
          equityDataLength: equityData?.length || 0,
          equityData: equityData
        });
        
        if (equityData && equityData.length > 0) {
          console.log('🔍 useMarketData - Processing equity data...');
          
          // Transform equity data to market data format
          const transformedData = equityData.map(transformEquityToMarketData);
          console.log('🔍 useMarketData - Transformed data:', transformedData);
          
          const processedData = processMarketDataWithColumnOrder(transformedData);
          console.log('🔍 useMarketData - Processed data:', processedData);
          
          setMarketData(processedData);
          latestDataRef.current = processedData;
          setDataCount(processedData.length);
          setLastUpdated(new Date().toLocaleTimeString());
          setStatus(MarketDataStatus.READY);
          
          console.log('🔍 useMarketData - State updated with new data, count:', processedData.length);
        } else {
          console.log('🔍 useMarketData - No equity data received or empty array, setting NO_DATA status');
          setMarketData([]);
          latestDataRef.current = [];
          setDataCount(0);
          setStatus(MarketDataStatus.NO_DATA);
        }
      },
      error: (err) => {
        console.error('🔍 useMarketData - Market Data Stream Error:', err);
        setError(err.message);
        setStatus(MarketDataStatus.ERROR);
      }
    });

    console.log('🔍 useMarketData - Subscription created:', subscription);

    return () => {
      console.log('🔍 useMarketData - Unsubscribing from equity data');
      subscription.unsubscribe();
    };
  }, [isConnected, viewId]);

  // Subscribe to last update timestamp for UI refresh
  useEffect(() => {
    console.log('🔍 useMarketData - Setting up last update timestamp subscription');
    
    const subscription = store.getLastUpdate$().subscribe({
      next: (timestamp) => {
        console.log('🔍 useMarketData - Received last update timestamp:', timestamp);
        if (timestamp > 0) {
          setLastUpdated(new Date(timestamp).toLocaleTimeString());
        }
      }
    });

    return () => {
      console.log('🔍 useMarketData - Unsubscribing from last update');
      subscription.unsubscribe();
    };
  }, []);

  const clearData = () => {
    console.log('🔍 useMarketData - clearData called');
    store.reset();
    setError(null);
    setStatus(MarketDataStatus.NO_DATA);
  };
  
  // Log current state periodically
  useEffect(() => {
    const interval = setInterval(() => {
      console.log('🔍 useMarketData - Current state:', {
        marketDataCount: marketData.length,
        status,
        error,
        dataCount,
        lastUpdated,
        isConnected
      });
    }, 10000); // Every 10 seconds

    return () => clearInterval(interval);
  }, [marketData.length, status, error, dataCount, lastUpdated, isConnected]);
  
  return {
    marketData,
    status,
    error,
    dataCount,
    lastUpdated,
    clearData,
  };
};