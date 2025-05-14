// src/hooks/useFundManager.ts
import { useContext } from 'react';
import { FundContext } from '../contexts/FundContext';

export const useFundManager = () => {
  const context = useContext(FundContext);
  if (context === null) {
    throw new Error('useFundManager must be used within a FundProvider');
  }
  return context;
};