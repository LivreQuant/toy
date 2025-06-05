import { BaseStateService } from './base-state-service';
export interface MarketData {
    price: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}
export interface ExchangeState {
    lastUpdated: number;
    symbols: Record<string, MarketData>;
}
export declare const initialExchangeState: ExchangeState;
export declare class ExchangeStateService extends BaseStateService<ExchangeState> {
    constructor();
    updateSymbols(symbols: Record<string, MarketData>): void;
    updateSymbol(symbol: string, data: MarketData): void;
    getSymbolData(symbol: string): MarketData | null;
    reset(): void;
}
export declare const exchangeState: ExchangeStateService;
