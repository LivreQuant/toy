// src/state/exchange-state.ts
import { BehaviorSubject, Observable } from 'rxjs';
import { map, distinctUntilChanged } from 'rxjs/operators';

import { getLogger } from '../boot/logging';

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
export class ExchangeStateService {
  private logger = getLogger('ExchangeStateService');
  
  private state$ = new BehaviorSubject<ExchangeState>(initialExchangeState);

  // Select a slice of the exchange state
  select<T>(selector: (state: ExchangeState) => T): Observable<T> {
    return this.state$.pipe(
      map(selector),
      distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))
    );
  }

  // Get the entire exchange state as an observable
  getState$(): Observable<ExchangeState> {
    return this.state$.asObservable();
  }

  // Get the current state snapshot
  getState(): ExchangeState {
    return this.state$.getValue();
  }

  // Update all symbols at once
  updateSymbols(symbols: Record<string, MarketData>): void {
    this.logger.debug(`Updating exchange symbols (count: ${Object.keys(symbols).length})`);
    this.state$.next({
      symbols,
      lastUpdated: Date.now()
    });
  }

  // Update a single symbol
  updateSymbol(symbol: string, data: MarketData): void {
    const currentState = this.getState();
    this.state$.next({
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
}

// Export singleton instance
export const exchangeState = new ExchangeStateService();