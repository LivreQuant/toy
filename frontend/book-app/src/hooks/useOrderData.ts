// src/hooks/useOrderData.ts
import { useState, useEffect } from 'react';
import { ExchangeDataStore } from '../stores/ExchangeDataStore';
import { OrderDataItem } from '../types/ExchangeData';
import { useConnection } from './useConnection';

export interface ProcessedOrderData extends OrderDataItem {
  created: Date;
  fillRate?: number;
  filledQuantity?: number;
}

export const useOrderData = () => {
  const [orders, setOrders] = useState<ProcessedOrderData[]>([]);
  const [dataCount, setDataCount] = useState<number>(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const { isConnected } = useConnection();
  const store = ExchangeDataStore.getInstance();

  useEffect(() => {
    if (!isConnected) {
      setOrders([]);
      setDataCount(0);
      setError('Not connected to data stream');
      return;
    }

    setError(null);

    // Subscribe to order updates
    const subscription = store.getOrders$().subscribe({
      next: (orderData: OrderDataItem[]) => {
        // Transform to match existing interface if needed
        const processedOrders: ProcessedOrderData[] = orderData.map(order => ({
          ...order,
          created: new Date(order.timestamp), // Convert timestamp to Date
          // Add additional computed fields if needed
        }));

        setOrders(processedOrders);
        setDataCount(processedOrders.length);
        setLastUpdated(new Date().toLocaleTimeString());
      },
      error: (err) => {
        console.error('Order Data Stream Error:', err);
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
    orders,
    dataCount,
    lastUpdated,
    error,
    clearData,
  };
};