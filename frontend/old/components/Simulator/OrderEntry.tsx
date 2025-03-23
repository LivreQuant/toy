// src/components/Simulator/OrderEntry.tsx
import React, { useState, useEffect } from 'react';
import { useConnection } from '../../contexts/ConnectionContext';
import './OrderEntry.css';

interface OrderEntryProps {
  selectedSymbol?: string;
  onOrderSubmit?: (order: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price: number;
    type: 'MARKET' | 'LIMIT';
  }) => void;
}

const OrderEntry: React.FC<OrderEntryProps> = ({ 
  selectedSymbol, 
  onOrderSubmit 
}) => {
  const [symbol, setSymbol] = useState(selectedSymbol || 'AAPL');
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [quantity, setQuantity] = useState<number>(100);
  const [price, setPrice] = useState<number | ''>('');
  const [orderType, setOrderType] = useState<'MARKET' | 'LIMIT'>('MARKET');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { canSubmitOrders, isConnected } = useConnection();
  
  // Update symbol when prop changes
  useEffect(() => {
    if (selectedSymbol) {
      setSymbol(selectedSymbol);
    }
  }, [selectedSymbol]);
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!canSubmitOrders) {
      setError('Order submission is currently disabled due to connection issues');
      return;
    }
    
    if (!symbol || !quantity || (orderType === 'LIMIT' && price === '')) {
      setError('Please fill out all required fields');
      return;
    }
    
    setIsSubmitting(true);
    setError(null);
    
    // Create order object
    const order = {
      symbol,
      side,
      quantity,
      price: orderType === 'MARKET' ? 0 : Number(price),
      type: orderType
    };
    
    // Submit order
    if (onOrderSubmit) {
      onOrderSubmit(order);
    }
    
    // Simulate API call
    setTimeout(() => {
      setIsSubmitting(false);
      // Reset form for market orders
      if (orderType === 'MARKET') {
        // Reset quantity but keep symbol and side
        setQuantity(100);
      }
    }, 500);
  };
  
  return (
    <div className="order-entry-container">
      <h2 className="order-entry-title">Order Entry</h2>
      
      {error && <div className="order-entry-error">{error}</div>}
      
      <form onSubmit={handleSubmit} className="order-entry-form">
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="symbol">Symbol</label>
            <input
              id="symbol"
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              disabled={isSubmitting || !isConnected}
              required
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="orderType">Type</label>
            <select
              id="orderType"
              value={orderType}
              onChange={(e) => setOrderType(e.target.value as 'MARKET' | 'LIMIT')}
              disabled={isSubmitting || !isConnected}
            >
              <option value="MARKET">Market</option>
              <option value="LIMIT">Limit</option>
            </select>
          </div>
        </div>
        
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="side">Side</label>
            <div className="side-selector">
              <button
                type="button"
                className={`side-button buy ${side === 'BUY' ? 'selected' : ''}`}
                onClick={() => setSide('BUY')}
                disabled={isSubmitting || !isConnected}
              >
                Buy
              </button>
              <button
                type="button"
                className={`side-button sell ${side === 'SELL' ? 'selected' : ''}`}
                onClick={() => setSide('SELL')}
                disabled={isSubmitting || !isConnected}
              >
                Sell
              </button>
            </div>
          </div>
          
          <div className="form-group">
            <label htmlFor="quantity">Quantity</label>
            <input
              id="quantity"
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(parseInt(e.target.value) || 0)}
              min={1}
              disabled={isSubmitting || !isConnected}
              required
            />
          </div>
          
          {orderType === 'LIMIT' && (
            <div className="form-group">
              <label htmlFor="price">Price</label>
              <input
                id="price"
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value === '' ? '' : Number(e.target.value))}
                step="0.01"
                min="0.01"
                disabled={isSubmitting || !isConnected}
                required={orderType === 'LIMIT'}
              />
            </div>
          )}
        </div>
        
        <div className="form-row">
          <button
            type="submit"
            className={`submit-button ${side.toLowerCase()}`}
            disabled={isSubmitting || !canSubmitOrders}
          >
            {isSubmitting ? 'Submitting...' : `${side} ${symbol}`}
          </button>
        </div>
      </form>
      
      <div className="quick-trade-buttons">
        <h3>Quick Trade</h3>
        <div className="quick-buttons">
          <button
            className="quick-button buy"
            onClick={() => {
              setSide('BUY');
              setOrderType('MARKET');
              setQuantity(100);
              setTimeout(() => handleSubmit({ preventDefault: () => {} } as React.FormEvent), 100);
            }}
            disabled={isSubmitting || !canSubmitOrders}
          >
            Buy 100 Market
          </button>
          <button
            className="quick-button sell"
            onClick={() => {
              setSide('SELL');
              setOrderType('MARKET');
              setQuantity(100);
              setTimeout(() => handleSubmit({ preventDefault: () => {} } as React.FormEvent), 100);
            }}
            disabled={isSubmitting || !canSubmitOrders}
          >
            Sell 100 Market
          </button>
        </div>
      </div>
    </div>
  );
};

export default OrderEntry;