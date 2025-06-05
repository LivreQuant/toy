// src/hooks/useExchangeState.ts
import { useExchangeState as useStateContext } from '../contexts/ExchangeStateContext';
import { exchangeState, MarketData } from '../state/exchange-state';

export function useExchangeState() {
  const state = useStateContext();
  
  return {
    // State values
    symbols: state.symbols,
    lastUpdated: state.lastUpdated,
    
    // Helper methods
    getSymbolData: (symbol: string): MarketData | null => state.symbols[symbol] || null,
    getAllSymbols: () => Object.keys(state.symbols),
    hasSymbol: (symbol: string) => !!state.symbols[symbol],
    
    // Update methods
    updateSymbol: exchangeState.updateSymbol.bind(exchangeState),
    updateSymbols: exchangeState.updateSymbols.bind(exchangeState)
  };
}