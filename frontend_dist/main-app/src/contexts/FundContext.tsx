// frontend_dist/main-app/src/contexts/FundContext.tsx
import React, { createContext, ReactNode } from 'react';
import { FundManager } from '../services/fund/fund-manager';
import { FundClient } from '@trading-app/api';
import { TokenManager } from '@trading-app/auth';

interface FundContextType {
  createFundProfile: (fundData: any) => Promise<{ success: boolean; fundId?: string; error?: string }>;
  getFundProfile: () => Promise<{ success: boolean; fund?: any; error?: string }>;
  updateFundProfile: (updates: any) => Promise<{ success: boolean; error?: string }>;
}

export const FundContext = createContext<FundContextType | null>(null);

export const FundProvider: React.FC<{ 
  children: ReactNode; 
  fundClient: FundClient; 
  tokenManager: TokenManager;
}> = ({ children, fundClient, tokenManager }) => {
  const fundManager = new FundManager(fundClient, tokenManager);

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