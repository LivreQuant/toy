// src/contexts/SimulatorStateContext.tsx
import React, { createContext, useContext, ReactNode } from 'react';

import { simulatorState, SimulatorState, initialSimulatorState } from '@trading-app/state';

import { useObservable } from '../hooks/useObservable';

// Create context with default value
const SimulatorStateContext = createContext<SimulatorState>(initialSimulatorState);

interface SimulatorStateProviderProps {
  children: ReactNode;
}

export const SimulatorStateProvider: React.FC<SimulatorStateProviderProps> = ({ children }) => {
  // Subscribe to simulator state changes
  const state = useObservable(simulatorState.getState$(), initialSimulatorState);
  
  return (
    <SimulatorStateContext.Provider value={state}>
      {children}
    </SimulatorStateContext.Provider>
  );
};

// Custom hook to use simulator state
export const useSimulatorState = () => {
  return useContext(SimulatorStateContext);
};