// src/components/Dashboard/Viewers/OrderBlotter/useOrderBlotterData.ts
import { useState, useRef, useEffect } from 'react';
import { ColumnStateService } from '../../AgGrid/columnStateService';
import { validateOrdersCsv, parseOrdersCsv } from './utils/orderCsvUtils';

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
  
  // Reference to the latest data for any background operations
  const latestDataRef = useRef<any[]>([]);

  // Process and transform order data with proper column order
  const processOrderWithColumnOrder = (orders: any[]) => {
    const columnStateService = ColumnStateService.getInstance();
    const savedColumnOrder = columnStateService.getOrderedColumns(viewId);
    
    if (!savedColumnOrder || savedColumnOrder.length === 0) {
      return orders;
    }
    
    // Transform orders to match the column order
    return orders.map(order => {
      const orderedOrder: {[key: string]: any} = {};
      
      // Explicitly map columns in the saved order
      savedColumnOrder.forEach(colId => {
        if (order.hasOwnProperty(colId)) {
          orderedOrder[colId] = order[colId];
        }
      });
      
      // Add any additional fields not in the saved order
      return {
        ...order,
        ...orderedOrder
      };
    });
  };

  const processFile = async (file: File) => {
    try {
      setStatus(OrderDataStatus.LOADING);
      setError(null);
      
      // Validate the CSV file structure
      await validateOrdersCsv(file);
      
      // Parse and validate the CSV file
      const { orders, hasErrors } = await parseOrdersCsv(file);
      
      if (orders.length === 0) {
        setError('No orders found in the CSV file.');
        setStatus(OrderDataStatus.ERROR);
        return false;
      }
      
      // Process orders with proper column order
      const processedOrders = processOrderWithColumnOrder(orders);
      
      // Update the state with the parsed orders
      setOrderData(processedOrders);
      latestDataRef.current = processedOrders;
      setDataCount(processedOrders.length);
      setLastUpdated(new Date().toLocaleTimeString());
      setIsDropzoneVisible(false);
      
      // If there are errors, show a notification but don't prevent displaying the grid
      if (hasErrors) {
        setStatus(OrderDataStatus.ERROR);
      } else {
        setStatus(OrderDataStatus.READY);
      }
      
      return true;
    } catch (error) {
      console.error('Error processing CSV file:', error);
      // Display the error message
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
  
  // Function to update order data
  const updateOrderData = (newOrderData: any[]) => {
    const processedOrders = processOrderWithColumnOrder(newOrderData);
    setOrderData(processedOrders);
    latestDataRef.current = processedOrders;
    setDataCount(processedOrders.length);
    setLastUpdated(new Date().toLocaleTimeString());
    
    if (processedOrders.length === 0) {
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