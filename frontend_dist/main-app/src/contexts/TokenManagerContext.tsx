// src/contexts/TokenManagerContext.tsx
import React, { createContext, ReactNode } from 'react';

import { TokenManager } from '../services/auth/token-manager';

// Create the context with an undefined default value
export const TokenManagerContext = createContext<TokenManager | undefined>(undefined);

// Provider component
interface TokenManagerProviderProps {
  tokenManager: TokenManager;
  children: ReactNode;
}

export const TokenManagerProvider: React.FC<TokenManagerProviderProps> = ({ 
  tokenManager, 
  children 
}) => {
  return (
    <TokenManagerContext.Provider value={tokenManager}>
      {children}
    </TokenManagerContext.Provider>
  );
};