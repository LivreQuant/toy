// frontend_dist/packages/state/src/exchange-state.ts
import { BaseStateService } from './base-state-service';

// Define equity data structure for the new format
export interface EquityData {
  symbol: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  trade_count: number;
  vwap: number;
  exchange_type: string;
  metadata: Record<string, any>;
}

// Keep the legacy MarketData for backward compatibility
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
  sequenceNumber: number;
  // Legacy symbols format
  symbols: Record<string, MarketData>;
  // New equity data format
  equityData: Record<string, EquityData>;
  // Track data source
  dataSource: 'legacy' | 'exchange_data';
}

// Initial exchange state
export const initialExchangeState: ExchangeState = {
  lastUpdated: 0,
  sequenceNumber: 0,
  symbols: {},
  equityData: {},
  dataSource: 'legacy'
};

// Exchange state service
export class ExchangeStateService extends BaseStateService<ExchangeState> {
  constructor() {
    super(initialExchangeState);
  }

  // NEW: Update equity data from exchange_data messages
  updateEquityData(equityDataArray: EquityData[]): void {
    this.logger.debug(`Updating equity data (count: ${equityDataArray.length})`);
    
    const equityDataMap: Record<string, EquityData> = {};
    equityDataArray.forEach(equity => {
      equityDataMap[equity.symbol] = equity;
    });

    this.updateState({
      equityData: equityDataMap,
      dataSource: 'exchange_data',
      lastUpdated: Date.now()
    });
  }

  // NEW: Update sequence number for delta tracking
  updateSequenceNumber(sequenceNumber: number): void {
    this.updateState({ sequenceNumber });
  }

  // LEGACY: Update all symbols at once (keep for backward compatibility)
  updateSymbols(symbols: Record<string, MarketData>): void {
    this.logger.debug(`Updating exchange symbols (count: ${Object.keys(symbols).length})`);
    this.updateState({
      symbols,
      dataSource: 'legacy',
      lastUpdated: Date.now()
    });
  }

  // LEGACY: Update a single symbol (keep for backward compatibility)
  updateSymbol(symbol: string, data: MarketData): void {
    const currentState = this.getState();
    this.updateState({
      lastUpdated: Date.now(),
      dataSource: 'legacy',
      symbols: {
        ...currentState.symbols,
        [symbol]: data
      }
    });
  }

  // NEW: Get equity data for a specific symbol
  getEquityData(symbol: string): EquityData | null {
    const currentState = this.getState();
    return currentState.equityData[symbol] || null;
  }

  // LEGACY: Get data for a specific symbol (keep for backward compatibility)
  getSymbolData(symbol: string): MarketData | null {
    const currentState = this.getState();
    return currentState.symbols[symbol] || null;
  }

  // NEW: Get all current equity data as array
  getAllEquityData(): EquityData[] {
    const currentState = this.getState();
    return Object.values(currentState.equityData);
  }

  // NEW: Transform equity data to legacy format for components that expect it
  getEquityDataAsMarketData(): Record<string, MarketData> {
    const currentState = this.getState();
    const marketDataMap: Record<string, MarketData> = {};
    
    Object.values(currentState.equityData).forEach(equity => {
      marketDataMap[equity.symbol] = {
        price: equity.close,
        open: equity.open,
        high: equity.high,
        low: equity.low,
        close: equity.close,
        volume: equity.volume
      };
    });
    
    return marketDataMap;
  }

  reset(): void {
    this.setState(initialExchangeState);
  }
}

// Export singleton instance
export const exchangeState = new ExchangeStateService();