// marketDataService.ts
export interface MarketData {
    instrument: string;
    price: number;
    change: number;
    changePercent: number;
    volume: number;
    exchange: string;
  }
  
  export class MarketDataService {
    private static mockStocks: MarketData[] = [
      {
        instrument: 'MSFT',
        price: 279.05,
        change: 1.53,
        changePercent: 0.55,
        volume: 321314,
        exchange: 'NASDAQ'
      },
      {
        instrument: 'AAPL',
        price: 195.67,
        change: -0.89,
        changePercent: -0.45,
        volume: 245123,
        exchange: 'NASDAQ'
      },
      {
        instrument: 'GOOGL',
        price: 128.42,
        change: 2.11,
        changePercent: 1.67,
        volume: 187654,
        exchange: 'NASDAQ'
      }
    ];
  
    static getMarketData(): MarketData[] {
      return this.mockStocks;
    }
  
    static getMarketDataForInstrument(instrument: string): MarketData | undefined {
      return this.mockStocks.find(stock => stock.instrument === instrument);
    }
  
    static simulateMarketMovement(): MarketData[] {
      return this.mockStocks.map(stock => ({
        ...stock,
        price: Number((stock.price + (Math.random() * 2 - 1)).toFixed(2)),
        change: Number((Math.random() * 2 - 1).toFixed(2)),
        changePercent: Number(((Math.random() * 2 - 1) / 100).toFixed(2)),
        volume: Math.floor(stock.volume * (0.9 + Math.random() * 0.2))
      }));
    }
  }