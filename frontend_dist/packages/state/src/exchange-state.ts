// src/exchange-state.ts
import { BaseStateService } from './base-state-service';

// Define market data structure
export interface MarketData {
  price: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Define the exchange state interface
export interface ExchangeState {
  lastUpdated: number;
  symbols: Record<string, MarketData>;
}

// Initial exchange state
export const initialExchangeState: ExchangeState = {
  lastUpdated: 0,
  symbols: {},
};

// Exchange state service
export class ExchangeStateService extends BaseStateService<ExchangeState> {
  constructor() {
    super(initialExchangeState);
  }

  // Update all symbols at once
  updateSymbols(symbols: Record<string, MarketData>): void {
    this.logger.debug(`Updating exchange symbols (count: ${Object.keys(symbols).length})`);
    this.setState({
      symbols,
      lastUpdated: Date.now()
    });
  }

  // Update a single symbol
  updateSymbol(symbol: string, data: MarketData): void {
    const currentState = this.getState();
    this.setState({
      lastUpdated: Date.now(),
      symbols: {
        ...currentState.symbols,
        [symbol]: data
      }
    });
  }

  // Get data for a specific symbol
  getSymbolData(symbol: string): MarketData | null {
    const currentState = this.getState();
    return currentState.symbols[symbol] || null;
  }

  reset(): void {
    this.setState(initialExchangeState);
  }
}

// Export singleton instance
export const exchangeState = new ExchangeStateService();