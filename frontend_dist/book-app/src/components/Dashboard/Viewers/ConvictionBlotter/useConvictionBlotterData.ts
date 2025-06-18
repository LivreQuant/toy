// src/components/Dashboard/Viewers/ConvictionBlotter/useConvictionBlotterData.ts
import { useState, useRef, useEffect } from 'react';
import { ColumnStateService } from '../../AgGrid/columnStateService';
import { validateConvictionsCsv, parseConvictionsCsv } from './utils/convictionCsvUtils';

export enum ConvictionDataStatus {
  READY = 'READY',
  LOADING = 'LOADING',
  ERROR = 'ERROR',
  NO_DATA = 'NO_DATA'
}

export const useConvictionData = (viewId: string) => {
  const [convictionData, setConvictionData] = useState<any[]>([]);
  const [status, setStatus] = useState<ConvictionDataStatus>(ConvictionDataStatus.NO_DATA);
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
      setStatus(ConvictionDataStatus.LOADING);
      setError(null);
      
      // Validate the CSV file structure
      await validateConvictionsCsv(file);
      
      // Parse and validate the CSV file
      const { convictions, hasErrors } = await parseConvictionsCsv(file);
      
      if (convictions.length === 0) {
        setError('No convictions found in the CSV file.');
        setStatus(ConvictionDataStatus.ERROR);
        return false;
      }
      
      const processedConvictions = processConvictionWithColumnOrder(convictions);
      
      setConvictionData(processedConvictions);
      latestDataRef.current = processedConvictions;
      setDataCount(processedConvictions.length);
      setLastUpdated(new Date().toLocaleTimeString());
      setIsDropzoneVisible(false);
      
      if (hasErrors) {
        setStatus(ConvictionDataStatus.ERROR);
      } else {
        setStatus(ConvictionDataStatus.READY);
      }
      
      return true;
    } catch (error) {
      console.error('Error processing CSV file:', error);
      setError(`${error instanceof Error ? error.message : 'Unknown error processing file'}`);
      setStatus(ConvictionDataStatus.ERROR);
      return false;
    }
  };

  const clearData = () => {
    setConvictionData([]);
    latestDataRef.current = [];
    setDataCount(0);
    setLastUpdated(null);
    setError(null);
    setStatus(ConvictionDataStatus.NO_DATA);
    setIsDropzoneVisible(true);
  };
  
  const updateConvictionData = (newConvictionData: any[]) => {
    console.log('[useConvictionData] updateConvictionData called with:', {
      newDataLength: newConvictionData.length,
      currentDataLength: convictionData.length,
      isDropzoneVisibleBefore: isDropzoneVisible,
      statusBefore: status
    });
    
    const processedConvictions = processConvictionWithColumnOrder(newConvictionData);
    console.log('[useConvictionData] Processed convictions:', {
      processedLength: processedConvictions.length,
      sample: processedConvictions.slice(0, 1)
    });
    
    setConvictionData(processedConvictions);
    latestDataRef.current = processedConvictions;
    setDataCount(processedConvictions.length);
    setLastUpdated(new Date().toLocaleTimeString());
    
    if (processedConvictions.length === 0) {
      console.log('[useConvictionData] No data, showing dropzone');
      setIsDropzoneVisible(true);
      setStatus(ConvictionDataStatus.NO_DATA);
    } else {
      console.log('[useConvictionData] Data available, hiding dropzone');
      setIsDropzoneVisible(false);
      setStatus(ConvictionDataStatus.READY);
    }
    
    console.log('[useConvictionData] State updated:', {
      dataCount: processedConvictions.length,
      isDropzoneVisible: processedConvictions.length === 0,
      status: processedConvictions.length === 0 ? 'NO_DATA' : 'READY'
    });
  };

  return {
    convictionData,
    status,
    error,
    dataCount,
    lastUpdated,
    isDropzoneVisible,
    processFile,
    clearData,
    updateConvictionData,
    setConvictionData
  };
};