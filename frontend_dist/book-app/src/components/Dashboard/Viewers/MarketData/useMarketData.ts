// src/components/Dashboard/Viewers/MarketData/useMarketData.ts
import { useState, useRef, useEffect } from 'react';
import { ConnectionManager } from '../../../../services/stream/manager/connectionManager';
import { StreamStatus } from '../../../../services/stream/services/exchangeDataStream';
import { MarketDataBar } from '../../../../protobufs/services/marketdataservice_pb';
import { ColumnStateService } from '../../AgGrid/columnStateService';

export enum MarketDataStatus {
 READY = 'READY',
 LOADING = 'LOADING',
 ERROR = 'ERROR',
 NO_DATA = 'NO_DATA'
}

export const useMarketData = (viewId: string) => {
 const [marketData, setMarketData] = useState<MarketDataBar[]>([]);
 const [status, setStatus] = useState<MarketDataStatus>(MarketDataStatus.NO_DATA);
 const [error, setError] = useState<string | null>(null);
 const [dataCount, setDataCount] = useState<number>(0);
 const [lastUpdated, setLastUpdated] = useState<string | null>(null);
 const [isDropzoneVisible, setIsDropzoneVisible] = useState<boolean>(true);
 
 const connectionManager = ConnectionManager.getInstance();
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

 // Handle stream status changes
 const handleStatus = (streamStatus: StreamStatus) => {
   switch (streamStatus) {
     case StreamStatus.CONNECTING:
       setStatus(MarketDataStatus.LOADING);
       break;
     case StreamStatus.CONNECTED:
       setStatus(MarketDataStatus.READY);
       break;
     case StreamStatus.DISCONNECTED:
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
     setIsDropzoneVisible(false);
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
   setIsDropzoneVisible(true);
 };

 useEffect(() => {
   // Initial data fetch
   const initialData = connectionManager.getLatestMarketData();
   if (initialData && initialData.length > 0) {
     handleMarketData(initialData);
   }

   // Add listeners
   connectionManager.addMarketDataListener(handleMarketData);
   
   // Check and handle current stream status
   const currentStatus = connectionManager.getMarketDataStatus();
   handleStatus(currentStatus);

   // Cleanup function
   return () => {
     connectionManager.removeMarketDataListener(handleMarketData);
   };
 }, []);

 const clearData = () => {
   setMarketData([]);
   latestDataRef.current = [];
   setDataCount(0);
   setLastUpdated(null);
   setError(null);
   setStatus(MarketDataStatus.NO_DATA);
   setIsDropzoneVisible(true);
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