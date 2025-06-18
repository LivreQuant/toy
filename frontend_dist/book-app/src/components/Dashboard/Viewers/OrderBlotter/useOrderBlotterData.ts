// src/components/Dashboard/Viewers/OrderBlotter/useOrderBlotterData.ts
import { useState, useRef, useEffect } from 'react';
import { ColumnStateService } from '../../AgGrid/columnStateService';
import { validateConvictionsCsv, parseConvictionsCsv } from './utils/convictionCsvUtils';

export enum OrderDataStatus {
  READY = 'READY',
  LOADING = 'LOADING',
  ERROR = 'ERROR',
  NO_DATA = 'NO_DATA'
}

export const useOrderData = (viewId: string) => {
  const [orderData, setOrderData] = useState<any[]>([]);
  const [status, setStatus] = useState<OrderDataStatus>(OrderDataStatus.NO_DATA);
  const [error, setError] = useState<string | null>(null);
  const [dataCount, setDataCount] = useState<number>(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isDropzoneVisible, setIsDropzoneVisible] = useState<boolean>(true);
  
  const latestDataRef = useRef<any[]>([]);

  // Process and transform conviction data with proper column order
  const processConvictionWithColumnOrder = (convictions: any[]) => {
    const columnStateService = ColumnStateService.getInstance();
    const savedColumnOrder = columnStateService.getOrderedColumns(viewId);
    
    if (!savedColumnOrder || savedColumnOrder.length === 0) {
      return convictions;
    }
    
    return convictions.map(conviction => {
      const orderedConviction: {[key: string]: any} = {};
      
      // Map columns in the saved order
      savedColumnOrder.forEach(colId => {
        if (conviction.hasOwnProperty(colId)) {
          orderedConviction[colId] = conviction[colId];
        }
      });
      
      return {
        ...conviction,
        ...orderedConviction
      };
    });
  };

  const processFile = async (file: File) => {
    try {
      setStatus(OrderDataStatus.LOADING);
      setError(null);
      
      // Validate the CSV file structure
      await validateConvictionsCsv(file);
      
      // Parse and validate the CSV file
      const { convictions, hasErrors } = await parseConvictionsCsv(file);
      
      if (convictions.length === 0) {
        setError('No convictions found in the CSV file.');
        setStatus(OrderDataStatus.ERROR);
        return false;
      }
      
      const processedConvictions = processConvictionWithColumnOrder(convictions);
      
      setOrderData(processedConvictions);
      latestDataRef.current = processedConvictions;
      setDataCount(processedConvictions.length);
      setLastUpdated(new Date().toLocaleTimeString());
      setIsDropzoneVisible(false);
      
      if (hasErrors) {
        setStatus(OrderDataStatus.ERROR);
      } else {
        setStatus(OrderDataStatus.READY);
      }
      
      return true;
    } catch (error) {
      console.error('Error processing CSV file:', error);
      setError(`${error instanceof Error ? error.message : 'Unknown error processing file'}`);
      setStatus(OrderDataStatus.ERROR);
      return false;
    }
  };

  const clearData = () => {
    setOrderData([]);
    latestDataRef.current = [];
    setDataCount(0);
    setLastUpdated(null);
    setError(null);
    setStatus(OrderDataStatus.NO_DATA);
    setIsDropzoneVisible(true);
  };
  
  const updateOrderData = (newConvictionData: any[]) => {
    const processedConvictions = processConvictionWithColumnOrder(newConvictionData);
    setOrderData(processedConvictions);
    latestDataRef.current = processedConvictions;
    setDataCount(processedConvictions.length);
    setLastUpdated(new Date().toLocaleTimeString());
    
    if (processedConvictions.length === 0) {
      setIsDropzoneVisible(true);
      setStatus(OrderDataStatus.NO_DATA);
    }
  };

  return {
    orderData,
    status,
    error,
    dataCount,
    lastUpdated,
    isDropzoneVisible,
    processFile,
    clearData,
    updateOrderData,
    setOrderData
  };
};