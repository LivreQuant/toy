// src/components/Dashboard/Viewers/MarketData/useMarketData.ts
import { useState, useRef, useEffect } from 'react';
import { useConnection } from '../../../../hooks/useConnection';
import { ColumnStateService } from '../../AgGrid/columnStateService';

export enum MarketDataStatus {
 READY = 'READY',
 LOADING = 'LOADING',
 ERROR = 'ERROR',
 NO_DATA = 'NO_DATA'
}

// Define MarketDataBar interface here since we removed protobuf
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

export const useMarketData = (viewId: string) => {
 const [marketData, setMarketData] = useState<MarketDataBar[]>([]);
 const [status, setStatus] = useState<MarketDataStatus>(MarketDataStatus.NO_DATA);
 const [error, setError] = useState<string | null>(null);
 const [dataCount, setDataCount] = useState<number>(0);
 const [lastUpdated, setLastUpdated] = useState<string | null>(null);
 
 // Use existing connection system
 const { connectionManager, isConnected, connectionState } = useConnection();
 const latestDataRef = useRef<MarketDataBar[]>([]);

 // Process and transform market data with proper column order
 const processMarketDataWithColumnOrder = (data: MarketDataBar[]) => {
   const columnStateService = ColumnStateService.getInstance();
   const savedColumnOrder = columnStateService.getOrderedColumns(viewId);
   
   if (!savedColumnOrder || savedColumnOrder.length === 0) {
     return data;
   }
   
   // Transform data to match the column order
   return data.map(bar => {
     const orderedBar: {[key: string]: any} = {};
     
     // Explicitly map columns in the saved order
     savedColumnOrder.forEach(colId => {
       if (bar.hasOwnProperty(colId)) {
         orderedBar[colId] = (bar as any)[colId];
       }
     });
     
     // Add any additional fields not in the saved order
     return {
       ...bar,
       ...orderedBar
     };
   });
 };

 // Handle connection status changes
 const handleStatus = (streamStatus: string) => {
   switch (streamStatus) {
     case 'CONNECTING':
       setStatus(MarketDataStatus.LOADING);
       break;
     case 'CONNECTED':
       setStatus(MarketDataStatus.READY);
       break;
     case 'DISCONNECTED':
       setStatus(MarketDataStatus.ERROR);
       setError('Market data stream disconnected');
       break;
     default:
       setStatus(MarketDataStatus.NO_DATA);
   }
 };

 // Handle market data updates
 const handleMarketData = (newData: MarketDataBar[]) => {
   if (newData && newData.length > 0) {
     const processedData = processMarketDataWithColumnOrder(newData);
     
     setMarketData(processedData);
     latestDataRef.current = processedData;
     setDataCount(processedData.length);
     setLastUpdated(new Date().toLocaleTimeString());
     setStatus(MarketDataStatus.READY);
   } else {
     setStatus(MarketDataStatus.NO_DATA);
   }
 };

 // Handle stream errors
 const handleError = (err: Error) => {
   console.error('Market Data Stream Error:', err);
   setError(err.message);
   setStatus(MarketDataStatus.ERROR);
 };

 useEffect(() => {
   if (!connectionManager || !isConnected) {
     setStatus(MarketDataStatus.NO_DATA);
     return;
   }

   // For now, just set status based on connection
   if (isConnected) {
     setStatus(MarketDataStatus.READY);
     // You can add mock data here for testing:
     const mockData: MarketDataBar[] = [
       {
         instrument: 'AAPL',
         exchange: 'NASDAQ',
         timestamp: Date.now(),
         open: 150.00,
         high: 152.50,
         low: 149.75,
         close: 151.25,
         volume: 1000000,
         change: 1.25,
         priceDirection: 1
       },
       {
         instrument: 'MSFT',
         exchange: 'NASDAQ', 
         timestamp: Date.now(),
         open: 280.00,
         high: 282.50,
         low: 279.75,
         close: 281.25,
         volume: 800000,
         change: 1.25,
         priceDirection: 1
       }
     ];
     
     handleMarketData(mockData);
   } else {
     setStatus(MarketDataStatus.ERROR);
     setError('Not connected to market data stream');
   }

   // TODO: Add real market data listeners when WebSocket integration is ready
   // connectionManager.addMarketDataListener(handleMarketData);
   
   // Handle current connection status
   if (connectionState) {
     handleStatus(connectionState.overallStatus);
   }

   // Cleanup function
   return () => {
     // TODO: Remove listeners when WebSocket integration is ready
     // connectionManager.removeMarketDataListener(handleMarketData);
   };
 }, [connectionManager, isConnected, connectionState, viewId]);

 const clearData = () => {
   setMarketData([]);
   latestDataRef.current = [];
   setDataCount(0);
   setLastUpdated(null);
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