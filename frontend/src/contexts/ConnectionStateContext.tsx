// src/contexts/ConnectionStateContext.tsx
import React, { createContext, useContext, ReactNode } from 'react';

import { connectionState, ConnectionState, initialConnectionState } from '../state/connection-state';

import { useObservable } from '../hooks/useObservable';

// Create context with default value
const ConnectionStateContext = createContext<ConnectionState>(initialConnectionState);

interface ConnectionStateProviderProps {
  children: ReactNode;
}

export const ConnectionStateProvider: React.FC<ConnectionStateProviderProps> = ({ children }) => {
  // Subscribe to connection state changes
  const state = useObservable(connectionState.getState$(), initialConnectionState);
  
  return (
    <ConnectionStateContext.Provider value={state}>
      {children}
    </ConnectionStateContext.Provider>
  );
};

// Custom hook to use connection state
export const useConnectionState = () => {
  return useContext(ConnectionStateContext);
};