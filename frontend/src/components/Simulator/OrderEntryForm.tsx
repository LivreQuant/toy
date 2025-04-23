// src/components/Simulator/OrderEntryForm.tsx
import React, { useState, useEffect } from 'react';

import { useOrderManager } from '../../contexts/OrderContext';

import { OrderSide, OrderType } from '../../api/order';

import { useToast } from '../../hooks/useToast';


// Add specific CSS for this form if needed: import './OrderEntryForm.css';

const OrderEntryForm: React.FC = () => {
  // Get connectionManager instance and the state slice
  const orderManager = useOrderManager();
  const { addToast } = useToast();

  const [symbol, setSymbol] = useState('BTC/USD');
  const [side, setSide] = useState<OrderSide>('BUY');
  const [type, setType] = useState<OrderType>('LIMIT');
  const [quantity, setQuantity] = useState<number | string>('');
  const [price, setPrice] = useState<number | string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleQuantityChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    if (value === '' || /^\d*\.?\d*$/.test(value)) {
       setQuantity(value);
    }
  };

   const handlePriceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
     const value = e.target.value;
     if (value === '' || /^\d*\.?\d*$/.test(value)) {
        setPrice(value);
     }
   };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    // Use derived canSubmit state
    if (!isSubmitting) return;

    const numQuantity = parseFloat(quantity.toString());
    const numPrice = type === 'LIMIT' ? parseFloat(price.toString()) : undefined;

    if (isNaN(numQuantity) || numQuantity <= 0) {
      addToast('error', 'Invalid quantity.');
      return;
    }
    if (type === 'LIMIT' && (numPrice === undefined || isNaN(numPrice) || numPrice <= 0)) {
       addToast('error', 'Invalid limit price.');
       return;
    }

    setIsSubmitting(true);
    addToast('info', `Submitting ${side} ${type} order for ${numQuantity} ${symbol}...`);

    try {
      const result = await orderManager.submitOrder({
        symbol,
        side,
        type,
        quantity: numQuantity,
        price: numPrice,
      });

      if (result.success) {
        addToast('success', `Order submitted successfully! ID: ${result.orderId}`);
        setQuantity('');
        setPrice('');
      } else {
        addToast('error', `Order submission failed: ${result.error || 'Unknown reason'}`);
      }
    } catch (error: any) {
      addToast('error', `Order submission error: ${error.message || 'An unexpected error occurred'}`);
      console.error("Order submission exception:", error); // Log full error for debugging
    } finally {
      setIsSubmitting(false);
    }
  };

  // Add basic CSS classes for buttons if not using a UI library
  const getButtonClass = (isActive: boolean) => {
     return `order-button ${isActive ? 'active' : ''}`;
  }

  return (
    <form onSubmit={handleSubmit} className="order-entry-form">
      <div className="form-group">
        <label htmlFor="symbol">Symbol</label>
        <input
          id="symbol"
          type="text"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          disabled={!isSubmitting}
          required
        />
      </div>

      <div className="form-group button-group">
        <label>Side</label>
        <div>
          <button type="button" onClick={() => setSide('BUY')} className={getButtonClass(side === 'BUY')} disabled={!isSubmitting}>Buy</button>
          <button type="button" onClick={() => setSide('SELL')} className={getButtonClass(side === 'SELL')} disabled={!isSubmitting}>Sell</button>
        </div>
      </div>

       <div className="form-group button-group">
        <label>Type</label>
        <div>
           <button type="button" onClick={() => setType('LIMIT')} className={getButtonClass(type === 'LIMIT')} disabled={!isSubmitting}>Limit</button>
           <button type="button" onClick={() => setType('MARKET')} className={getButtonClass(type === 'MARKET')} disabled={!isSubmitting}>Market</button>
        </div>
      </div>

      <div className="form-group">
        <label htmlFor="quantity">Quantity</label>
        <input
          id="quantity"
          type="text"
          inputMode="decimal"
          value={quantity}
          onChange={handleQuantityChange}
          placeholder="0.00"
          disabled={!isSubmitting}
          required
        />
      </div>

       {type === 'LIMIT' && (
         <div className="form-group">
             <label htmlFor="price">Limit Price</label>
             <input
                id="price"
                type="text"
                inputMode="decimal"
                value={price}
                onChange={handlePriceChange}
                placeholder="0.00"
                disabled={!isSubmitting}
                required={type === 'LIMIT'} // Required only for limit orders
             />
         </div>
       )}

      <button type="submit" disabled={!isSubmitting} className="submit-button">
        {isSubmitting ? 'Submitting...' : `Submit ${side} Order`}
      </button>
    </form>
  );
};

export default OrderEntryForm;