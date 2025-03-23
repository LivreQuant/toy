// src/pages/SimulatorPage.tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useConnection } from '../contexts/ConnectionContext';
import { submitOrder, getOrderStatus, getMarketData } from '../services/grpc/simulator';
import ConnectionIndicator from '../components/ConnectionIndicator';

// Mock data types
interface Order {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  price: number;
  quantity: number;
  status: string;
  filledQuantity: number;
  avgPrice: number;
  timestamp: number;
}

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

const SimulatorPage: React.FC = () => {
  const { 
    isConnected, 
    isConnecting, 
    sessionId, 
    simulatorId, 
    simulatorStatus,
    canSubmitOrders,
    connectionQuality,
    error: connectionError
  } = useConnection();
  
  const [orders, setOrders] = useState<Order[]>([]);
  const [marketData, setMarketData] = useState<Record<string, MarketDataItem>>({});
  const [streamActive, setStreamActive] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [submittingOrder, setSubmittingOrder] = useState(false);
  const [orderError, setOrderError] = useState<string | null>(null);
  const navigate = useNavigate();
  const [warningMessage, setWarningMessage] = useState<string | null>(null);
  
  const token = localStorage.getItem('token');
  
  // Add warning message state
  const [warningMessage, setWarningMessage] = useState<string | null>(null);
  
  // Update warning message based on connection state
  useEffect(() => {
    if (!isConnected && isConnecting) {
      setWarningMessage("Reconnecting to server - order submission disabled");
    } else if (!isConnected) {
      setWarningMessage("Disconnected from server - order submission disabled");
    } else if (simulatorStatus !== 'RUNNING') {
      setWarningMessage(`Simulator is ${simulatorStatus.toLowerCase()} - order submission disabled`);
    } else if (connectionQuality === 'poor') {
      setWarningMessage("Poor connection quality - order submission disabled");
    } else if (connectionQuality === 'degraded') {
      setWarningMessage("Connection quality degraded - please be cautious when submitting orders");
    } else if (!canSubmitOrders) {
      setWarningMessage("Cannot submit orders at this time - please check connection");
    } else {
      setWarningMessage(null);
    }
  }, [isConnected, isConnecting, simulatorStatus, connectionQuality, canSubmitOrders]);

  
  useEffect(() => {
    if (!token || !sessionId || !simulatorId) {
      navigate('/home');
      return;
    }
    
    // Check if we need to reconnect - handled by ConnectionContext
    
    // Start market data stream if not already active
    if (isConnected && !streamActive && !streamError) {
      startMarketDataStream();
    }
    
    // Clean up on unmount
    return () => {
      // Stop market data stream
      if (streamActive) {
        console.log('Stopping market data stream');
        // In a real implementation, would cancel the gRPC stream
      }
    };
  }, [isConnected, simulatorId, sessionId, token, navigate, streamActive, streamError]);
  
  const startMarketDataStream = async () => {
    if (!token || !sessionId || !simulatorId) return;
    
    try {
      setStreamActive(true);
      setStreamError(null);
      
      // This is a simplified example - actual implementation would use gRPC streaming
      const symbols = ['AAPL', 'MSFT', 'AMZN', 'GOOGL'];
      
      // Simulating streaming market data with a timer
      const updateInterval = setInterval(() => {
        // Only update if connected
        if (isConnected) {
          const updatedData: Record<string, MarketDataItem> = {};
          
          symbols.forEach(symbol => {
            const currentPrice = marketData[symbol]?.lastPrice || getRandomPrice(symbol);
            const priceDelta = (Math.random() - 0.5) * 2; // Random price movement
            const newPrice = Math.max(0.01, currentPrice + priceDelta);
            
            updatedData[symbol] = {
              symbol,
              bid: newPrice - 0.01,
              ask: newPrice + 0.01,
              bidSize: Math.floor(Math.random() * 1000) + 100,
              askSize: Math.floor(Math.random() * 1000) + 100,
              lastPrice: newPrice,
              lastSize: Math.floor(Math.random() * 100) + 10,
              timestamp: Date.now()
            };
          });
          
          setMarketData(prev => ({...prev, ...updatedData}));
        }
      }, 1000);
      
      // Return cleanup function
      return () => clearInterval(updateInterval);
    } catch (error) {
      console.error('Failed to start market data stream', error);
      setStreamActive(false);
      setStreamError('Failed to connect to market data stream');
    }
  };
  
  const getRandomPrice = (symbol: string): number => {
    // Generate pseudo-random prices based on symbol
    const baseMap: Record<string, number> = {
      'AAPL': 150,
      'MSFT': 250,
      'AMZN': 100,
      'GOOGL': 120
    };
    
    return baseMap[symbol] || 100;
  };
  
  const handleSubmitOrder = async (symbol: string, side: 'BUY' | 'SELL', price: number, quantity: number) => {
    // Check if order submission is allowed
    if (!canSubmitOrders) {
      setOrderError("Order submission is currently disabled due to connection issues");
      return;
    }
    
    if (!token || !sessionId || !simulatorId) {
      setOrderError("Session information missing. Please return to home page and try again.");
      return;
    }
    
    try {
      setSubmittingOrder(true);
      setOrderError(null);
      
      const response = await submitOrder(token, sessionId, symbol, side, price, quantity);
      
      if (response.success) {
        const newOrder: Order = {
          id: response.orderId,
          symbol,
          side,
          price,
          quantity,
          status: 'NEW',
          filledQuantity: 0,
          avgPrice: 0,
          timestamp: Date.now()
        };
        
        setOrders(prevOrders => [newOrder, ...prevOrders]);
        
        // Poll for order status updates
        pollOrderStatus(response.orderId);
      } else {
        setOrderError(response.errorMessage || "Failed to submit order");
        console.error('Order submission failed', response.errorMessage);
      }
    } catch (error) {
      setOrderError("Network error while submitting order. Please try again.");
      console.error('Failed to submit order', error);
    } finally {
      setSubmittingOrder(false);
    }
  };
  
  const pollOrderStatus = async (orderId: string) => {
    if (!token || !sessionId) return;
    
    const checkStatus = async () => {
      try {
        const response = await getOrderStatus(token, sessionId, orderId);
        
        // Update order in state
        setOrders(prevOrders => 
          prevOrders.map(order => 
            order.id === orderId 
              ? { 
                  ...order, 
                  status: response.status, 
                  filledQuantity: response.filledQuantity,
                  avgPrice: response.avgPrice
                }
              : order
          )
        );
        
        // Continue polling if order is still active
        if (['NEW', 'PARTIALLY_FILLED'].includes(response.status)) {
          setTimeout(checkStatus, 1000);
        }
      } catch (error) {
        console.error('Failed to get order status', error);
        
        // If we're still connected, try again
        if (isConnected) {
          setTimeout(checkStatus, 2000); // Longer delay on error
        }
      }
    };
    
    checkStatus();
  };
  
  const handleBackToHome = () => {
    navigate('/home');
  };
  
  // Simplified UI for testing
  return (
    <div className="simulator-page">
      <ConnectionIndicator />
      
      <div className="header">
        <h1>Trading Simulator</h1>
        <div className="status-indicator">
          <span className={`simulator-status ${simulatorStatus.toLowerCase()}`}>
            Simulator: {simulatorStatus}
          </span>
        </div>
        <button onClick={handleBackToHome}>Back to Home</button>
      </div>
      
      {(connectionError || orderError) && (
        <div className="error-message">
          {connectionError || orderError}
        </div>
      )}
      
      {warningMessage && (
        <div className="warning-banner">
          <i className="warning-icon">⚠️</i>
          <span>{warningMessage}</span>
        </div>
      )}
      
      <div className="market-data-section">
        <h2>Market Data</h2>
        {streamError && <div className="error-message">{streamError}</div>}
        
        <div className="market-data-grid">
          {Object.values(marketData).map(item => (
            <div key={item.symbol} className="market-data-card">
              <div className="symbol">{item.symbol}</div>
              <div className="price">Last: ${item.lastPrice.toFixed(2)}</div>
              <div className="bid-ask">
                Bid: ${item.bid.toFixed(2)} x {item.bidSize} | 
                Ask: ${item.ask.toFixed(2)} x {item.askSize}
              </div>
            </div>
          ))}
          
          {Object.keys(marketData).length === 0 && (
            <div className="loading-data">
              {isConnected ? "Loading market data..." : "Cannot load market data - disconnected"}
            </div>
          )}
        </div>
      </div>
      
      <div className="order-entry-section">
        <h2>Order Entry</h2>
        {/* Simplified order entry form */}
        <div className="order-buttons">
          <button 
            onClick={() => handleSubmitOrder('AAPL', 'BUY', marketData['AAPL']?.ask || 150, 100)}
            disabled={!canSubmitOrders || submittingOrder}
            className={(!canSubmitOrders || submittingOrder) ? 'button-disabled' : ''}
          >
            Buy 100 AAPL at Market
          </button>
          <button 
            onClick={() => handleSubmitOrder('MSFT', 'SELL', marketData['MSFT']?.bid || 250, 50)}
            disabled={!canSubmitOrders || submittingOrder}
            className={(!canSubmitOrders || submittingOrder) ? 'button-disabled' : ''}
          >
            Sell 50 MSFT at Market
          </button>
          <button 
            onClick={() => handleSubmitOrder('AMZN', 'BUY', marketData['AMZN']?.ask || 100, 10)}
            disabled={!canSubmitOrders || submittingOrder}
            className={(!canSubmitOrders || submittingOrder) ? 'button-disabled' : ''}
          >
            Buy 10 AMZN at Market
          </button>
          <button 
            onClick={() => handleSubmitOrder('GOOGL', 'SELL', marketData['GOOGL']?.bid || 120, 20)}
            disabled={!canSubmitOrders || submittingOrder}
            className={(!canSubmitOrders || submittingOrder) ? 'button-disabled' : ''}
          >
            Sell 20 GOOGL at Market
          </button>
        </div>
        
        {submittingOrder && (
          <div className="submitting-order">Submitting order...</div>
        )}
      </div>
      
      <div className="orders-section">
        <h2>Orders</h2>
        <table className="orders-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Quantity</th>
              <th>Price</th>
              <th>Status</th>
              <th>Filled</th>
              <th>Avg Price</th>
            </tr>
          </thead>
          <tbody>
            {orders.map(order => (
              <tr key={order.id}>
                <td>{order.id.substring(0, 8)}...</td>
                <td>{order.symbol}</td>
                <td className={order.side === 'BUY' ? 'buy' : 'sell'}>
                  {order.side}
                </td>
                <td>{order.quantity}</td>
                <td>${order.price.toFixed(2)}</td>
                <td>{order.status}</td>
                <td>{order.filledQuantity}</td>
                <td>${order.avgPrice > 0 ? order.avgPrice.toFixed(2) : '-'}</td>
              </tr>
            ))}
            {orders.length === 0 && (
              <tr>
                <td colSpan={8}>No orders yet</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default SimulatorPage;