// src/hooks/useTokenManager.ts
import { useContext } from 'react';
import { TokenManagerContext } from '../contexts/TokenManagerContext';

export const useTokenManager = () => {
  const context = useContext(TokenManagerContext);
  if (context === undefined) {
    throw new Error('useTokenManager must be used within a TokenManagerProvider');
  }
  return context;
};