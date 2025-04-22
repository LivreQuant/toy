// src/contexts/AuthStateContext.tsx
import React, { createContext, useContext, ReactNode } from 'react';
import { useObservable } from '../hooks/useObservable';
import { authState, AuthState, initialAuthState } from '../state/auth-state';

// Create context with default value
const AuthStateContext = createContext<AuthState>(initialAuthState);

interface AuthStateProviderProps {
  children: ReactNode;
}

export const AuthStateProvider: React.FC<AuthStateProviderProps> = ({ children }) => {
  // Subscribe to auth state changes
  const state = useObservable(authState.getState$(), initialAuthState);
  
  return (
    <AuthStateContext.Provider value={state}>
      {children}
    </AuthStateContext.Provider>
  );
};

// Custom hook to use auth state
export const useAuthState = () => {
  return useContext(AuthStateContext);
};