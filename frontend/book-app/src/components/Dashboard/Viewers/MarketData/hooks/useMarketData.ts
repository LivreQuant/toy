// frontend_dist/book-app/src/components/Dashboard/Viewers/MarketData/hooks/useMarketData.ts
import { useState, useRef, useEffect, useCallback } from 'react';
import { useConnection } from '../../../../../contexts/ConnectionContext';
import { ColumnStateService } from '../../../AgGrid/services/columnStateService';
import { ExchangeDataStore } from '../../../../../stores/ExchangeDataStore';
import { EquityDataItem } from '../../../../../types/ExchangeData';
import { exchangeState } from '@trading-app/state';
import { getLogger } from '@trading-app/logging';

const logger = getLogger('useMarketData');

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
  const transformed = {
    instrument: equity.symbol,
    exchange: equity.exchange_type,
    timestamp: Date.now(),
    open: equity.open,
    high: equity.high,
    low: equity.low,
    close: equity.close,
    volume: equity.volume,
    change: undefined, // Calculate if needed
    priceDirection: undefined // Calculate if needed
  };
  
  logger.debug('📊 HOOK: Transformed equity data', {
    from: { symbol: equity.symbol, close: equity.close },
    to: { instrument: transformed.instrument, close: transformed.close }
  });
  
  return transformed;
}

export const useMarketData = (viewId: string) => {
  logger.info('🔍 HOOK: useMarketData hook initialized', { viewId });
  
  const [marketData, setMarketData] = useState<MarketDataBar[]>([]);
  const [status, setStatus] = useState<MarketDataStatus>(MarketDataStatus.NO_DATA);
  const [error, setError] = useState<string | null>(null);
  const [dataCount, setDataCount] = useState<number>(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  
  const { connectionManager, isConnected } = useConnection();
  const latestDataRef = useRef<MarketDataBar[]>([]);
  const store = ExchangeDataStore.getInstance();

  logger.info('🔍 HOOK: Initial state', {
    viewId,
    isConnected,
    hasConnectionManager: !!connectionManager,
    hasStore: !!store,
    initialStatus: status
  });

  // Process and transform market data with proper column order
  const processMarketDataWithColumnOrder = useCallback((data: MarketDataBar[]) => {
    logger.info('🔍 HOOK: processMarketDataWithColumnOrder START', {
      inputDataCount: data.length,
      viewId
    });
    
    const columnStateService = ColumnStateService.getInstance();
    const savedColumnOrder = columnStateService.getOrderedColumns(viewId);
    
    if (!savedColumnOrder || savedColumnOrder.length === 0) {
      logger.info('🔍 HOOK: No saved column order, returning data as-is');
      return data;
    }
    
    logger.debug('🔍 HOOK: Applying column order', {
      columnOrder: savedColumnOrder,
      dataCount: data.length
    });
    
    const processedData = data.map(bar => {
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
    
    logger.info('🔍 HOOK: processMarketDataWithColumnOrder COMPLETE', {
      outputDataCount: processedData.length
    });
    
    return processedData;
  }, [viewId]);

  // Process data from either source
  const processEquityData = useCallback((equityData: EquityDataItem[], source: string) => {
    logger.info(`📊 HOOK: processEquityData START - Processing data from ${source}`, {
      equityDataLength: equityData?.length || 0,
      source,
      sampleEquity: equityData?.[0]
    });
    
    if (equityData && equityData.length > 0) {
      logger.info('📊 HOOK: Transforming equity data to market data format...');
      
      // Transform equity data to market data format
      const transformedData = equityData.map((equity, index) => {
        const transformed = transformEquityToMarketData(equity);
        if (index < 3) { // Log first 3 transformations
          logger.debug(`📊 HOOK: Transformation ${index + 1}:`, {
            original: { symbol: equity.symbol, close: equity.close },
            transformed: { instrument: transformed.instrument, close: transformed.close }
          });
        }
        return transformed;
      });
      
      logger.info('📊 HOOK: Applying column order processing...');
      const processedData = processMarketDataWithColumnOrder(transformedData);
      
      logger.info('📊 HOOK: Updating component state...', {
        processedDataCount: processedData.length,
        sampleData: processedData.slice(0, 2)
      });
      
      setMarketData(processedData);
      latestDataRef.current = processedData;
      setDataCount(processedData.length);
      setLastUpdated(new Date().toLocaleTimeString());
      setStatus(MarketDataStatus.READY);
      setError(null);
      
      logger.info('✅ HOOK: processEquityData COMPLETE - Component state updated', {
        source,
        finalDataCount: processedData.length,
        status: 'READY'
      });
    } else {
      logger.warn('📊 HOOK: No equity data or empty array received', {
        source,
        equityData: equityData
      });
      setStatus(MarketDataStatus.NO_DATA);
      setMarketData([]);
      setDataCount(0);
      setError(`No data available from ${source}`);
    }
  }, [processMarketDataWithColumnOrder]);

  // Clear data function
  const clearData = useCallback(() => {
    logger.info('🧹 HOOK: clearData called - resetting all state');
    
    setMarketData([]);
    setStatus(MarketDataStatus.NO_DATA);
    setError(null);
    setDataCount(0);
    setLastUpdated(null);
    latestDataRef.current = [];
    
    // Also reset the store
    try {
      store.reset();
      logger.info('✅ HOOK: Store reset successfully');
    } catch (resetError: any) {
      logger.error('❌ HOOK: Error resetting store', {
        error: resetError.message
      });
    }
    
    logger.info('✅ HOOK: clearData complete');
  }, [store]);

  // DUAL SUBSCRIPTION APPROACH: Subscribe to both ExchangeDataStore AND global exchangeState
  useEffect(() => {
    logger.info('🔍 HOOK: EFFECT START - Setting up data subscriptions', {
      viewId,
      isConnected,
      hasStore: !!store
    });
    
    if (!isConnected) {
      logger.warn('🔍 HOOK: Not connected - setting NO_DATA state');
      setStatus(MarketDataStatus.NO_DATA);
      setError('Not connected to data stream');
      setMarketData([]);
      setDataCount(0);
      return;
    }

    logger.info('🔍 HOOK: Connection established - setting up subscriptions...');
    setStatus(MarketDataStatus.LOADING);
    setError(null);

    const subscriptions: any[] = [];

    // SUBSCRIPTION 1: ExchangeDataStore (primary data source)
    logger.info('🔍 HOOK: Setting up ExchangeDataStore subscription...');
    try {
      const storeSubscription = store.getEquityData$().subscribe({
        next: (equityData: EquityDataItem[]) => {
          logger.info('📊 HOOK: STORE DATA RECEIVED', {
            source: 'ExchangeDataStore',
            count: equityData?.length || 0,
            symbols: equityData?.map(e => e.symbol).slice(0, 5) || [],
            samplePrices: equityData?.slice(0, 3).map(e => `${e.symbol}:${e.close}`) || []
          });
          
          if (equityData && equityData.length > 0) {
            processEquityData(equityData, 'ExchangeDataStore');
          } else {
            logger.info('📊 HOOK: Empty data from ExchangeDataStore');
          }
        },
        error: (err) => {
          logger.error('❌ HOOK: ExchangeDataStore subscription error', {
            error: err.message,
            stack: err.stack
          });
          setError(`Store error: ${err.message}`);
          setStatus(MarketDataStatus.ERROR);
        }
      });
      subscriptions.push(storeSubscription);
      logger.info('✅ HOOK: ExchangeDataStore subscription established');
    } catch (storeError: any) {
      logger.error('❌ HOOK: Failed to set up ExchangeDataStore subscription', {
        error: storeError.message
      });
    }

    // SUBSCRIPTION 2: Global exchangeState (fallback/alternative source) - FIXED
    logger.info('🔍 HOOK: Setting up global exchangeState subscription...');
    try {
      // FIXED: Use getState$() instead of subscribe()
      const globalStateSubscription = exchangeState.getState$().subscribe((state) => {
        logger.info('📊 HOOK: GLOBAL STATE RECEIVED', {
          source: 'GlobalExchangeState',
          equityDataCount: Object.keys(state.equityData).length,
          symbolsCount: Object.keys(state.symbols).length,
          dataSource: state.dataSource,
          lastUpdated: state.lastUpdated,
          sequenceNumber: state.sequenceNumber
        });
        
        // Convert global state equity data to array format
        const equityArray = Object.values(state.equityData);
        if (equityArray.length > 0) {
          logger.info('📊 HOOK: Processing equity data from global state...');
          processEquityData(equityArray as EquityDataItem[], 'GlobalExchangeState');
        } else {
          logger.debug('📊 HOOK: No equity data in global state');
        }
      });
      subscriptions.push(globalStateSubscription);
      logger.info('✅ HOOK: Global exchangeState subscription established');
    } catch (globalError: any) {
      logger.error('❌ HOOK: Failed to set up global state subscription', {
        error: globalError.message
      });
    }

    // Initial data check from both sources
    logger.info('🔍 HOOK: Checking for initial data from both sources...');
    
    // Check ExchangeDataStore first
    try {
      const currentStoreData = store.getCurrentEquityData();
      logger.info('🔍 HOOK: Initial ExchangeDataStore check', {
        count: currentStoreData.length,
        symbols: currentStoreData.map(e => e.symbol).slice(0, 5)
      });
      
      if (currentStoreData.length > 0) {
        logger.info('📊 HOOK: Found initial data in ExchangeDataStore');
        processEquityData(currentStoreData, 'ExchangeDataStore-Initial');
      } else {
        logger.info('🔍 HOOK: No initial data in ExchangeDataStore, checking global state...');
        
        // Check global state as fallback
        const globalState = exchangeState.getState();
        const globalEquityArray = Object.values(globalState.equityData);
        logger.info('🔍 HOOK: Initial global state check', {
          count: globalEquityArray.length,
          dataSource: globalState.dataSource,
          lastUpdated: globalState.lastUpdated
        });
        
        if (globalEquityArray.length > 0) {
          logger.info('📊 HOOK: Found initial data in global state');
          processEquityData(globalEquityArray as EquityDataItem[], 'GlobalExchangeState-Initial');
        } else {
          logger.warn('📊 HOOK: No initial data found in either source');
        }
      }
    } catch (initialCheckError: any) {
      logger.error('❌ HOOK: Error during initial data check', {
        error: initialCheckError.message
      });
    }

    // Cleanup function
    return () => {
      logger.info('🔍 HOOK: EFFECT CLEANUP - Unsubscribing from all subscriptions', {
        subscriptionCount: subscriptions.length
      });
      
      subscriptions.forEach((sub, index) => {
        try {
          if (sub && typeof sub.unsubscribe === 'function') {
            sub.unsubscribe();
            logger.debug(`🔍 HOOK: Unsubscribed from subscription ${index}`);
          }
        } catch (unsubError: any) {
          logger.error(`❌ HOOK: Error unsubscribing from subscription ${index}`, {
            error: unsubError.message
          });
        }
      });
      
      logger.info('✅ HOOK: All subscriptions cleaned up');
    };
  }, [isConnected, processEquityData]);

  // Debug method
  const getDebugInfo = useCallback(() => {
    const storeData = store.getCurrentEquityData();
    const globalState = exchangeState.getState();
    
    const debugInfo = {
      hookState: {
        isConnected,
        status,
        dataCount,
        lastUpdated,
        error
      },
      storeData: {
        count: storeData.length,
        symbols: storeData.map(e => e.symbol).slice(0, 5)
      },
      globalState: {
        count: Object.keys(globalState.equityData).length,
        dataSource: globalState.dataSource,
        lastUpdated: globalState.lastUpdated,
        sequenceNumber: globalState.sequenceNumber
      }
    };
    
    logger.info('🔍 HOOK: Debug info requested', debugInfo);
    return debugInfo;
  }, [isConnected, status, dataCount, lastUpdated, error]);

  logger.debug('🔍 HOOK: useMarketData returning state', {
    marketDataCount: marketData.length,
    status,
    error,
    dataCount,
    lastUpdated,
    isConnected
  });

  return {
    marketData,
    status,
    error,
    dataCount,
    lastUpdated,
    isConnected,
    clearData,
    getDebugInfo
  };
};