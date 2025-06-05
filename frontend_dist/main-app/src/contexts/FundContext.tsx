// src/contexts/FundContext.tsx
import React, { createContext, ReactNode } from 'react';
import { FundManager } from '../services/fund/fund-manager';
import { fundApi } from '../api/api-client';
import { tokenManager } from '../api/api-client';

interface FundContextType {
  createFundProfile: (fundData: any) => Promise<{ success: boolean; fundId?: string; error?: string }>;
  getFundProfile: () => Promise<{ success: boolean; fund?: any; error?: string }>;
  updateFundProfile: (updates: any) => Promise<{ success: boolean; error?: string }>;
}

export const FundContext = createContext<FundContextType | null>(null);

export const FundProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const fundManager = new FundManager(fundApi, tokenManager);

  const contextValue: FundContextType = {
    createFundProfile: fundManager.createFundProfile.bind(fundManager),
    getFundProfile: fundManager.getFundProfile.bind(fundManager),
    updateFundProfile: fundManager.updateFundProfile.bind(fundManager),
  };

  return (
    <FundContext.Provider value={contextValue}>
      {children}
    </FundContext.Provider>
  );
};