// src/exchange-state.ts
import { BaseStateService } from './base-state-service';
// Initial exchange state
export const initialExchangeState = {
    lastUpdated: 0,
    symbols: {},
};
// Exchange state service
export class ExchangeStateService extends BaseStateService {
    constructor() {
        super(initialExchangeState);
    }
    // Update all symbols at once
    updateSymbols(symbols) {
        this.logger.debug(`Updating exchange symbols (count: ${Object.keys(symbols).length})`);
        this.setState({
            symbols,
            lastUpdated: Date.now()
        });
    }
    // Update a single symbol
    updateSymbol(symbol, data) {
        const currentState = this.getState();
        this.setState({
            lastUpdated: Date.now(),
            symbols: Object.assign(Object.assign({}, currentState.symbols), { [symbol]: data })
        });
    }
    // Get data for a specific symbol
    getSymbolData(symbol) {
        const currentState = this.getState();
        return currentState.symbols[symbol] || null;
    }
    reset() {
        this.setState(initialExchangeState);
    }
}
// Export singleton instance
export const exchangeState = new ExchangeStateService();
