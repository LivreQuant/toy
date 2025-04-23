// src/services/data/exchange-data-cache.ts
import { getLogger } from '../../boot/logging';

export class ExchangeDataCache {
  private logger = getLogger('ExchangeDataCache');
  private exchangeData: Record<string, any> = {}; 
  
  /**
   * Updates the internal cache of exchange data.
   * @param data - The new exchange data.
   */
  public updateExchangeData(data: Record<string, any>): void {
    this.exchangeData = { ...this.exchangeData, ...data };
    this.logger.debug('Exchange data cache updated', { 
      newDataSymbols: Object.keys(data) 
    });
  }

  /**
   * Retrieves a copy of the cached exchange data.
   * @returns A copy of the exchange data object.
   */
  public getExchangeData(): Record<string, any> {
    return { ...this.exchangeData };
  }

  /**
   * Clears the entire exchange data cache.
   */
  public clearCache(): void {
    this.exchangeData = {};
    this.logger.debug('Exchange data cache cleared');
  }

  /**
   * Retrieves data for a specific symbol.
   * @param symbol - The trading symbol to retrieve data for.
   * @returns The data for the specified symbol or undefined.
   */
  public getSymbolData(symbol: string): any | undefined {
    return this.exchangeData[symbol];
  }
}