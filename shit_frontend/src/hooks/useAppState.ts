// src/hooks/useAppState.ts
import { useState, useEffect } from 'react';
import { appState, AppState } from '../services/state/app-state.service';

// Hook to select any part of the state
export function useAppState<T>(selector: (state: AppState) => T): T {
  const [value, setValue] = useState<T>(selector(appState.getState()));

  useEffect(() => {
    const subscription = appState.select(selector).subscribe(newValue => {
      setValue(newValue);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [selector]);

  return value;
}

// Specialized hooks for common state slices
export function useConnectionState() {
  return useAppState(state => state.connection);
}

export function useAuthState() {
  return useAppState(state => state.auth);
}

export function useExchangeData() {
  return useAppState(state => state.exchange.data);
}

export function usePortfolio() {
  return useAppState(state => state.portfolio);
}