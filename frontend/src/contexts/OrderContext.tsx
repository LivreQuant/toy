// src/contexts/OrderContext.tsx
import React, { createContext, useContext, ReactNode } from 'react';

import { OrderManager } from '../services/orders/order-manager';

// Create context with undefined default value
const OrderContext = createContext<OrderManager | undefined>(undefined);

// Provider component
interface OrderProviderProps {
  orderManager: OrderManager;
  children: ReactNode;
}

export const OrderProvider: React.FC<OrderProviderProps> = ({ 
  orderManager, 
  children 
}) => {
  return (
    <OrderContext.Provider value={orderManager}>
      {children}
    </OrderContext.Provider>
  );
};

// Custom hook to use the order manager
export const useOrderManager = () => {
  const context = useContext(OrderContext);
  if (context === undefined) {
    throw new Error('useOrderManager must be used within an OrderProvider');
  }
  return context;
};