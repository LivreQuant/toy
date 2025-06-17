// RiskDataService.ts
export interface RiskMetrics {
    instrument: string;
    beta: number;
    volatility: number;
    var: number; // Value at Risk
    sharpeRatio: number;
    correlationSPY: number;
    maxDrawdown: number;
    sector: string;
  }
  
  export class RiskDataService {
    private static mockRiskData: RiskMetrics[] = [
      {
        instrument: 'MSFT',
        beta: 1.24,
        volatility: 19.67,
        var: 4.32,
        sharpeRatio: 1.85,
        correlationSPY: 0.82,
        maxDrawdown: 15.6,
        sector: 'Technology'
      },
      {
        instrument: 'AAPL',
        beta: 1.35,
        volatility: 22.34,
        var: 5.18,
        sharpeRatio: 1.67,
        correlationSPY: 0.79,
        maxDrawdown: 18.2,
        sector: 'Technology'
      },
      {
        instrument: 'GOOGL',
        beta: 1.18,
        volatility: 21.05,
        var: 4.87,
        sharpeRatio: 1.53,
        correlationSPY: 0.75,
        maxDrawdown: 17.3,
        sector: 'Technology'
      },
      {
        instrument: 'AMZN',
        beta: 1.47,
        volatility: 25.64,
        var: 6.32,
        sharpeRatio: 1.42,
        correlationSPY: 0.81,
        maxDrawdown: 22.8,
        sector: 'Consumer Cyclical'
      },
      {
        instrument: 'TSLA',
        beta: 2.15,
        volatility: 45.78,
        var: 12.65,
        sharpeRatio: 0.98,
        correlationSPY: 0.68,
        maxDrawdown: 35.4,
        sector: 'Automotive'
      }
    ];
  
    static getRiskData(): RiskMetrics[] {
      return this.mockRiskData;
    }
  
    static getPortfolioRiskSummary() {
      // Calculate portfolio-level risk metrics
      const avgBeta = this.calculateWeightedAverage('beta');
      const avgVolatility = this.calculateWeightedAverage('volatility');
      const avgVaR = this.calculateWeightedAverage('var');
      const avgSharpe = this.calculateWeightedAverage('sharpeRatio');
      const avgCorrelation = this.calculateWeightedAverage('correlationSPY');
      const maxDrawdown = Math.max(...this.mockRiskData.map(item => item.maxDrawdown));
  
      return {
        portfolioBeta: avgBeta,
        portfolioVolatility: avgVolatility,
        portfolioVaR: avgVaR,
        portfolioSharpe: avgSharpe,
        portfolioCorrelation: avgCorrelation,
        portfolioMaxDrawdown: maxDrawdown
      };
    }
  
    static updateRiskData(): RiskMetrics[] {
      // Simulate small changes to risk metrics
      this.mockRiskData = this.mockRiskData.map(risk => ({
        ...risk,
        beta: Number((risk.beta + (Math.random() * 0.1 - 0.05)).toFixed(2)),
        volatility: Number((risk.volatility + (Math.random() * 0.5 - 0.25)).toFixed(2)),
        var: Number((risk.var + (Math.random() * 0.2 - 0.1)).toFixed(2)),
        sharpeRatio: Number((risk.sharpeRatio + (Math.random() * 0.1 - 0.05)).toFixed(2)),
        correlationSPY: Number((risk.correlationSPY + (Math.random() * 0.04 - 0.02)).toFixed(2)),
        maxDrawdown: Number((risk.maxDrawdown + (Math.random() * 0.3 - 0.15)).toFixed(1))
      }));
      
      return this.mockRiskData;
    }
  
    private static calculateWeightedAverage(metricName: keyof RiskMetrics): number {
        // For simplicity, we'll use equal weights
        // In a real app, you'd weight by position size
        const sum = this.mockRiskData.reduce((total, item) => {
          // Make sure we're only summing numeric properties
          const value = item[metricName];
          return total + (typeof value === 'number' ? value : 0);
        }, 0);
        
        return Number((sum / this.mockRiskData.length).toFixed(2));
      }
  }