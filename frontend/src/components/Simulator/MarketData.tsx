// src/components/Simulator/MarketData.tsx
import React from 'react';
import { useSession } from '../../contexts/SessionContext';
import './MarketData.css';

interface MarketDataProps {
  onSymbolSelect?: (symbol: string) => void;
}

const MarketData: React.FC<MarketDataProps> = ({ onSymbolSelect }) => {
  const { isConnected, marketData, connectionQuality } = useSession();
  const [selectedSymbol, setSelectedSymbol] = React.useState<string | null>(null);
  
  const handleSymbolClick = (symbol: string) => {
    setSelectedSymbol(symbol);
    if (onSymbolSelect) {
      onSymbolSelect(symbol);
    }
  };
  
  if (!isConnected) {
    return (
      <div className="market-data-container">
        <h2 className="market-data-title">Market Data</h2>
        <div className="market-data-disconnected">
          Not connected to market data stream
        </div>
      </div>
    );
  }
  
  if (Object.keys(marketData).length === 0) {
    return (
      <div className="market-data-container">
        <h2 className="market-data-title">Market Data</h2>
        <div className="market-data-loading">
          Loading market data...
        </div>
      </div>
    );
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
              <div className={`price`}>
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
          </div>
        ))}
      </div>
      
      {connectionQuality === 'poor' && (
        <div className="market-data-warning">
          Poor connection quality - data may be delayed
        </div>
      )}
    </div>
  );
};

export default MarketData;