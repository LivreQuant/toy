// PortfolioDataService.ts
export interface PortfolioPosition {
    instrument: string;
    exchange: string;
    quantity: number;
    entryPrice: number;
    currentPrice: number;
    marketValue: number;
    pnl: number;
    pnlPercent: number;
    sector: string;
  }
  
  export class PortfolioDataService {
    private static mockPositions: PortfolioPosition[] = [
      {
        instrument: 'MSFT',
        exchange: "SIP",
        quantity: 100,
        entryPrice: 265.32,
        currentPrice: 279.05,
        marketValue: 27905.00,
        pnl: 1373.00,
        pnlPercent: 5.17,
        sector: 'Technology'
      },
      {
        instrument: 'AAPL',
        exchange: "SIP",
        quantity: 150,
        entryPrice: 183.45,
        currentPrice: 195.67,
        marketValue: 29350.50,
        pnl: 1833.00,
        pnlPercent: 6.66,
        sector: 'Technology'
      },
      {
        instrument: 'GOOGL',
        exchange: "SIP",
        quantity: 50,
        entryPrice: 120.35,
        currentPrice: 128.42,
        marketValue: 6421.00,
        pnl: 403.50,
        pnlPercent: 6.71,
        sector: 'Technology'
      },
      {
        instrument: 'AMZN',
        exchange: "SIP",
        quantity: 30,
        entryPrice: 134.25,
        currentPrice: 142.98,
        marketValue: 4289.40,
        pnl: 261.90,
        pnlPercent: 6.50,
        sector: 'Consumer Cyclical'
      },
      {
        instrument: 'TSLA',
        exchange: "SIP",
        quantity: 40,
        entryPrice: 225.78,
        currentPrice: 208.45,
        marketValue: 8338.00,
        pnl: -691.20,
        pnlPercent: -7.67,
        sector: 'Automotive'
      }
    ];
  
    static getPortfolioPositions(): PortfolioPosition[] {
      return this.mockPositions;
    }
  
    static getPortfolioSummary() {
      const totalMarketValue = this.mockPositions.reduce((sum, position) => sum + position.marketValue, 0);
      const totalPnL = this.mockPositions.reduce((sum, position) => sum + position.pnl, 0);
      const initialValue = totalMarketValue - totalPnL;
      const totalPnLPercent = (totalPnL / initialValue) * 100;
  
      return {
        positionCount: this.mockPositions.length,
        totalMarketValue: totalMarketValue,
        totalPnL: totalPnL,
        totalPnLPercent: totalPnLPercent
      };
    }
  
    static updatePortfolioWithMarketData(marketData: { instrument: string, price: number }[]) {
      this.mockPositions = this.mockPositions.map(position => {
        const updatedPrice = marketData.find(data => data.instrument === position.instrument)?.price;
        
        if (updatedPrice) {
          const newMarketValue = position.quantity * updatedPrice;
          const newPnl = newMarketValue - (position.quantity * position.entryPrice);
          const newPnlPercent = (newPnl / (position.quantity * position.entryPrice)) * 100;
          
          return {
            ...position,
            currentPrice: updatedPrice,
            marketValue: newMarketValue,
            pnl: newPnl,
            pnlPercent: newPnlPercent
          };
        }
        
        return position;
      });
      
      return this.mockPositions;
    }
  }