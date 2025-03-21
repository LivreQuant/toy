// src/components/Simulator/MarketData.tsx
import React, { useEffect, useState } from 'react';
import { useConnection } from '../../contexts/ConnectionContext';
import Loading from '../Common/Loading';
import './MarketData.css';

interface MarketDataItem {
  symbol: string;
  bid: number;
  ask: number;
  bidSize: number;
  askSize: number;
  lastPrice: number;
  lastSize: number;
  timestamp: number;
}

interface MarketDataProps {
  onSymbolSelect?: (symbol: string) => void;
}

const MarketData: React.FC<MarketDataProps> = ({ onSymbolSelect }) => {
  const [marketData, setMarketData] = useState<Record<string, MarketDataItem>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  
  const { isConnected, sessionId, simulatorId, canSubmitOrders } = useConnection();
  
  useEffect(() => {
    if (!isConnected || !sessionId || !simulatorId) {
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    // This would be your actual market data stream
    // For now, we'll simulate it with an interval
    const symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META'];
    
    // Initialize with empty data
    const initialData: Record<string, MarketDataItem> = {};
    symbols.forEach(symbol => {
      initialData[symbol] = {
        symbol,
        bid: 0,
        ask: 0,
        bidSize: 0,
        askSize: 0,
        lastPrice: 0,
        lastSize: 0,
        timestamp: Date.now()
      };
    });
    
    setMarketData(initialData);
    setIsLoading(false);
    
    // Simulate market data updates
    const updateInterval = setInterval(() => {
      if (!isConnected) return;
      
      const updatedData: Record<string, MarketDataItem> = {};
      
      symbols.forEach(symbol => {
        const basePrice = getBasePrice(symbol);
        const spread = basePrice * 0.0005; // 0.05% spread
        const bidSize = Math.floor(Math.random() * 1000) + 100;
        const askSize = Math.floor(Math.random() * 1000) + 100;
        
        // Random price movement
        const priceDelta = (Math.random() - 0.5) * basePrice * 0.002;
        const lastPrice = marketData[symbol]?.lastPrice || basePrice;
        const newPrice = Math.max(0.01, lastPrice + priceDelta);
        
        updatedData[symbol] = {
          symbol,
          bid: newPrice - spread,
          ask: newPrice + spread,
          bidSize,
          askSize,
          lastPrice: newPrice,
          lastSize: Math.floor(Math.random() * 100) + 10,
          timestamp: Date.now()
        };
      });
      
      setMarketData(prevData => ({...prevData, ...updatedData}));
    }, 1000);
    
    return () => clearInterval(updateInterval);
  }, [isConnected, sessionId, simulatorId]);
  
  const getBasePrice = (symbol: string): number => {
    switch (symbol) {
      case 'AAPL': return 150;
      case 'MSFT': return 250;
      case 'GOOGL': return 120;
      case 'AMZN': return 100;
      case 'TSLA': return 200;
      case 'META': return 180;
      default: return 100;
    }
  };
  
  const handleSymbolClick = (symbol: string) => {
    setSelectedSymbol(symbol);
    if (onSymbolSelect) {
      onSymbolSelect(symbol);
    }
  };
  
  if (isLoading) {
    return <Loading message="Loading market data..." />;
  }
  
  if (error) {
    return <div className="market-data-error">{error}</div>;
  }
  
  return (
    <div className="market-data-container">
      <h2 className="market-data-title">Market Data</h2>
      
      <div className="market-data-grid">
        {Object.values(marketData).map(item => (
          <div 
            key={item.symbol} 
            className={`market-data-card ${selectedSymbol === item.symbol ? 'selected' : ''}`}
            onClick={() => handleSymbolClick(item.symbol)}
          >
            <div className="symbol-row">
              <div className="symbol">{item.symbol}</div>
              <div className={`price ${item.lastPrice > (marketData[item.symbol]?.lastPrice || 0) ? 'up' : 'down'}`}>
                ${item.lastPrice.toFixed(2)}
              </div>
            </div>
            
            <div className="bid-ask-row">
              <div className="bid">
                <span className="label">Bid:</span>
                <span className="value">${item.bid.toFixed(2)} × {item.bidSize}</span>
              </div>
              <div className="ask">
                <span className="label">Ask:</span>
                <span className="value">${item.ask.toFixed(2)} × {item.askSize}</span>
              </div>
            </div>
            
            <div className="last-trade">
              <span className="label">Last:</span>
              <span className="value">{item.lastSize} @ ${item.lastPrice.toFixed(2)}</span>
            </div>
          </div>
        ))}
      </div>
      
      {!canSubmitOrders && (
        <div className="market-data-warning">
          Order submission disabled - check connection status
        </div>
      )}
    </div>
  );
};

export default MarketData;