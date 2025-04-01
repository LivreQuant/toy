// src/components/Simulator/MarketData.tsx
import React, { useState, useEffect } from 'react';
import { useConnection } from '../../contexts/ConnectionContext';
import './MarketData.css';

// Enhanced interface to match the new SSE data structure
interface MarketDataItem {
  symbol: string;
  price: number;
  change: number;
  bid: number;
  ask: number;
  bidSize: number;
  askSize: number;
  volume: number;
  timestamp: number;
}

const MarketData: React.FC = () => {
  const { isConnected, marketData } = useConnection();
  const [marketDataList, setMarketDataList] = useState<MarketDataItem[]>([]);

  // Convert marketData object to list whenever it updates
  useEffect(() => {
    if (marketData) {
      const dataList = Object.values(marketData);
      setMarketDataList(dataList);
    }
  }, [marketData]);

  if (!isConnected) {
    return (
      <div className="market-data-container">
        <h2>Market Data</h2>
        <div className="market-data-disconnected">
          Not connected to market data stream
        </div>
      </div>
    );
  }

  return (
    <div className="market-data-container">
      <h2>Market Data</h2>
      <table className="market-data-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Price</th>
            <th>Change</th>
            <th>Bid</th>
            <th>Ask</th>
            <th>Bid Size</th>
            <th>Ask Size</th>
            <th>Volume</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {marketDataList.map((item) => (
            <tr key={item.symbol}>
              <td>{item.symbol}</td>
              <td>${item.price.toFixed(2)}</td>
              <td style={{ color: item.change >= 0 ? 'green' : 'red' }}>
                {item.change.toFixed(2)}
              </td>
              <td>${item.bid.toFixed(2)}</td>
              <td>${item.ask.toFixed(2)}</td>
              <td>{item.bidSize}</td>
              <td>{item.askSize}</td>
              <td>{item.volume}</td>
              <td>{new Date(item.timestamp).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default MarketData;