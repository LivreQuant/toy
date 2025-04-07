import React, { useState, useEffect } from 'react';
import { useConnection } from '../../hooks/useConnection';
import { useToast } from '../../hooks/useToast';
import { OrderSide, OrderType } from '../../api/order'; // Import types
// Add specific CSS for this form if needed: import './OrderEntryForm.css';

const OrderEntryForm: React.FC = () => {
  const { connectionManager, connectionState } = useConnection();
  const { addToast } = useToast();

  const [symbol, setSymbol] = useState('BTC/USD'); // Default or fetched symbol
  const [side, setSide] = useState<OrderSide>('BUY');
  const [type, setType] = useState<OrderType>('LIMIT');
  const [quantity, setQuantity] = useState<number | string>('');
  const [price, setPrice] = useState<number | string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isConnected = connectionState?.isConnected ?? false;
  const isSimulatorRunning = connectionState?.simulatorStatus === 'RUNNING';
  const canSubmit = isConnected && isSimulatorRunning;

  // Reset form when connection/simulator stops
  useEffect(() => {
    if (!canSubmit) {
      // Optionally clear form fields or just disable submission
      // setSymbol(''); // etc.
      setIsSubmitting(false);
    }
  }, [canSubmit]);

  const handleQuantityChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    // Allow empty string or positive numbers
    if (value === '' || /^\d*\.?\d*$/.test(value)) {
       setQuantity(value);
    }
  };

   const handlePriceChange = (e: React.ChangeEvent<HTMLInputElement>) => {
     const value = e.target.value;
     // Allow empty string or positive numbers for price if LIMIT order
     if (value === '' || /^\d*\.?\d*$/.test(value)) {
        setPrice(value);
     }
   };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit || isSubmitting) return;

    const numQuantity = parseFloat(quantity.toString());
    const numPrice = type === 'LIMIT' ? parseFloat(price.toString()) : undefined;

    if (isNaN(numQuantity) || numQuantity <= 0) {
      addToast('error', 'Invalid quantity.');
      return;
    }
    if (type === 'LIMIT' && (isNaN(numPrice as number) || (numPrice as number) <= 0)) {
       addToast('error', 'Invalid limit price.');
       return;
    }


    setIsSubmitting(true);
    addToast('info', `Submitting ${side} ${type} order for ${numQuantity} ${symbol}...`);

    try {
      const result = await connectionManager.submitOrder({
        symbol,
        side,
        type,
        quantity: numQuantity,
        price: numPrice,
      });

      if (result.success) {
        addToast('success', `Order submitted successfully! ID: ${result.orderId}`);
        // Clear form on success
        setQuantity('');
        setPrice('');
      } else {
        addToast('error', `Order submission failed: ${result.error || 'Unknown reason'}`);
      }
    } catch (error: any) {
      addToast('error', `Order submission error: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Symbol Input/Selector (can be enhanced) */}
      <div className="form-group">
        <label htmlFor="symbol">Symbol</label>
        <input
          id="symbol"
          type="text"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          disabled={!canSubmit || isSubmitting}
          required
        />
      </div>

      {/* Side Selection */}
      <div className="form-group">
        <label>Side</label>
        <div>
          <button type="button" onClick={() => setSide('BUY')} className={side === 'BUY' ? 'active' : ''} disabled={!canSubmit || isSubmitting}>Buy</button>
          <button type="button" onClick={() => setSide('SELL')} className={side === 'SELL' ? 'active' : ''} disabled={!canSubmit || isSubmitting}>Sell</button>
          {/* Add specific styling for active button */}
        </div>
      </div>

       {/* Type Selection */}
      <div className="form-group">
        <label>Type</label>
        <div>
           <button type="button" onClick={() => setType('LIMIT')} className={type === 'LIMIT' ? 'active' : ''} disabled={!canSubmit || isSubmitting}>Limit</button>
           <button type="button" onClick={() => setType('MARKET')} className={type === 'MARKET' ? 'active' : ''} disabled={!canSubmit || isSubmitting}>Market</button>
        </div>
      </div>


      {/* Quantity Input */}
      <div className="form-group">
        <label htmlFor="quantity">Quantity</label>
        <input
          id="quantity"
          type="text" // Use text to allow intermediate decimal points
          inputMode="decimal" // Hint for mobile keyboards
          value={quantity}
          onChange={handleQuantityChange}
          placeholder="0.00"
          disabled={!canSubmit || isSubmitting}
          required
        />
      </div>

       {/* Price Input (Conditional for LIMIT orders) */}
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
                disabled={!canSubmit || isSubmitting}
                required={type === 'LIMIT'}
             />
         </div>
       )}

      <button type="submit" disabled={!canSubmit || isSubmitting}>
        {isSubmitting ? 'Submitting...' : `Submit ${side} Order`}
      </button>
      {!canSubmit && <p style={{fontSize: '0.9em', color: '#777', marginTop: '10px'}}>Connect and start simulator to trade.</p>}
    </form>
  );
};

export default OrderEntryForm;