// src/contexts/ExchangeStateContext.tsx
import React, { createContext, useContext, ReactNode } from 'react';

import { exchangeState, ExchangeState, initialExchangeState } from '@trading-app/state';

import { useObservable } from '../hooks/useObservable';

// Create context with default value
const ExchangeStateContext = createContext<ExchangeState>(initialExchangeState);

interface ExchangeStateProviderProps {
  children: ReactNode;
}

export const ExchangeStateProvider: React.FC<ExchangeStateProviderProps> = ({ children }) => {
  // Subscribe to exchange state changes
  const state = useObservable(exchangeState.getState$(), initialExchangeState);
  
  return (
    <ExchangeStateContext.Provider value={state}>
      {children}
    </ExchangeStateContext.Provider>
  );
};

// Custom hook to use exchange state
export const useExchangeState = () => {
  return useContext(ExchangeStateContext);
};