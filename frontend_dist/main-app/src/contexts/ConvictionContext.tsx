// src/contexts/ConvictionContext.tsx
import React, { createContext, useContext, ReactNode } from 'react';

import { ConvictionManager } from '../services/convictions/conviction-manager';

// Create context with undefined default value
const ConvictionContext = createContext<ConvictionManager | undefined>(undefined);

// Provider component
interface ConvictionProviderProps {
  convictionManager: ConvictionManager;
  children: ReactNode;
}

export const ConvictionProvider: React.FC<ConvictionProviderProps> = ({ 
  convictionManager, 
  children 
}) => {
  return (
    <ConvictionContext.Provider value={convictionManager}>
      {children}
    </ConvictionContext.Provider>
  );
};

// Custom hook to use the conviction manager
export const useConvictionManager = () => {
  const context = useContext(ConvictionContext);
  if (context === undefined) {
    throw new Error('useConvictionManager must be used within an ConvictionProvider');
  }
  return context;
};