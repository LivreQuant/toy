// src/components/Simulator/CsvOrderUpload.tsx
import React, { useState, useCallback, useRef } from 'react';
import { useToast } from '../../hooks/useToast';
import { useOrderManager } from '../../contexts/OrderContext';
import './CsvOrderUpload.css';

type Operation = 'SUBMIT' | 'CANCEL';

interface OrderData {
  symbol?: string;
  side?: 'BUY' | 'SELL';
  type?: 'MARKET' | 'LIMIT';
  quantity?: number;
  price?: number;
  orderId?: string;
}

const CsvOrderUpload: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [orders, setOrders] = useState<OrderData[]>([]);
  const [operation, setOperation] = useState<Operation>('SUBMIT');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { addToast } = useToast();
  const orderManager = useOrderManager();

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const processSubmitCsv = useCallback((content: string): OrderData[] => {
    const lines = content.trim().split('\n');
    if (lines.length === 0) return [];

    // Extract header and check required columns
    const header = lines[0].split(',').map(col => col.trim().toLowerCase());
    const requiredColumns = ['symbol', 'side', 'type', 'quantity'];
    const missingColumns = requiredColumns.filter(col => !header.includes(col));
    
    if (missingColumns.length > 0) {
      addToast('error', `CSV is missing required columns: ${missingColumns.join(', ')}`);
      return [];
    }

    // Map column indices
    const columnMap = {
      symbol: header.indexOf('symbol'),
      side: header.indexOf('side'),
      type: header.indexOf('type'),
      quantity: header.indexOf('quantity'),
      price: header.indexOf('price')
    };

    // Process data rows
    const parsedOrders: OrderData[] = [];
    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) continue;
      
      const values = lines[i].split(',').map(val => val.trim());
      
      // Validate required values
      if (values.length < requiredColumns.length) {
        addToast('warning', `Skipping row ${i+1}: insufficient columns`);
        continue;
      }

      const side = values[columnMap.side].toUpperCase();
      const type = values[columnMap.type].toUpperCase();
      
      // Validate side and type
      if (side !== 'BUY' && side !== 'SELL') {
        addToast('warning', `Skipping row ${i+1}: invalid side '${side}' (must be BUY or SELL)`);
        continue;
      }
      
      if (type !== 'MARKET' && type !== 'LIMIT') {
        addToast('warning', `Skipping row ${i+1}: invalid type '${type}' (must be MARKET or LIMIT)`);
        continue;
      }

      // Parse quantity
      const quantity = parseFloat(values[columnMap.quantity]);
      if (isNaN(quantity) || quantity <= 0) {
        addToast('warning', `Skipping row ${i+1}: invalid quantity '${values[columnMap.quantity]}'`);
        continue;
      }

      // For LIMIT orders, price is required
      let price: number | undefined = undefined;
      if (type === 'LIMIT') {
        if (columnMap.price === -1 || !values[columnMap.price]) {
          addToast('warning', `Skipping row ${i+1}: price is required for LIMIT orders`);
          continue;
        }
        
        price = parseFloat(values[columnMap.price]);
        if (isNaN(price) || price <= 0) {
          addToast('warning', `Skipping row ${i+1}: invalid price '${values[columnMap.price]}'`);
          continue;
        }
      }

      parsedOrders.push({
        symbol: values[columnMap.symbol],
        side: side as 'BUY' | 'SELL',
        type: type as 'MARKET' | 'LIMIT',
        quantity,
        price
      });
    }

    return parsedOrders;
  }, [addToast]);

  const processCancelCsv = useCallback((content: string): OrderData[] => {
    const lines = content.trim().split('\n');
    if (lines.length === 0) return [];

    // Extract header and check required columns
    const header = lines[0].split(',').map(col => col.trim().toLowerCase());
    
    if (!header.includes('orderid')) {
      addToast('error', 'CSV is missing required column: orderId');
      return [];
    }

    const orderIdIndex = header.indexOf('orderid');
    
    // Process data rows
    const parsedOrders: OrderData[] = [];
    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) continue;
      
      const values = lines[i].split(',').map(val => val.trim());
      
      // Validate required values
      if (values.length <= orderIdIndex) {
        addToast('warning', `Skipping row ${i+1}: missing orderId`);
        continue;
      }

      const orderId = values[orderIdIndex];
      if (!orderId) {
        addToast('warning', `Skipping row ${i+1}: empty orderId`);
        continue;
      }

      parsedOrders.push({ orderId });
    }

    return parsedOrders;
  }, [addToast]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.type === 'text/csv') {
      setFile(droppedFile);
      
      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target?.result as string;
        const processor = operation === 'SUBMIT' ? processSubmitCsv : processCancelCsv;
        const parsedOrders = processor(content);
        setOrders(parsedOrders);
        
        if (parsedOrders.length > 0) {
          addToast('success', `Loaded ${parsedOrders.length} ${operation === 'SUBMIT' ? 'orders' : 'cancellations'} from CSV`);
        } else {
          addToast('warning', `No valid ${operation === 'SUBMIT' ? 'orders' : 'cancellations'} found in CSV`);
        }
      };
      
      reader.readAsText(droppedFile);
    } else {
      addToast('error', 'Please drop a CSV file');
    }
  }, [operation, processSubmitCsv, processCancelCsv, addToast]);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    
    const selectedFile = e.target.files[0];
    if (selectedFile.type === 'text/csv') {
      setFile(selectedFile);
      
      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target?.result as string;
        const processor = operation === 'SUBMIT' ? processSubmitCsv : processCancelCsv;
        const parsedOrders = processor(content);
        setOrders(parsedOrders);
        
        if (parsedOrders.length > 0) {
          addToast('success', `Loaded ${parsedOrders.length} ${operation === 'SUBMIT' ? 'orders' : 'cancellations'} from CSV`);
        } else {
          addToast('warning', `No valid ${operation === 'SUBMIT' ? 'orders' : 'cancellations'} found in CSV`);
        }
      };
      
      reader.readAsText(selectedFile);
    } else {
      addToast('error', 'Please select a CSV file');
    }
  }, [operation, processSubmitCsv, processCancelCsv, addToast]);

  const handleBrowseClick = useCallback(() => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, []);

  const handleOperationChange = useCallback((newOperation: Operation) => {
    if (operation !== newOperation) {
      setOperation(newOperation);
      setFile(null);
      setOrders([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [operation]);

  const handleSubmit = useCallback(async () => {
    if (orders.length === 0 || isSubmitting) return;
    
    setIsSubmitting(true);
    
    try {
      if (operation === 'SUBMIT') {
        addToast('info', `Submitting ${orders.length} orders...`);
        
        // Filter out any undefined properties and prepare submit data
        const submitOrders = orders.map(order => ({
          symbol: order.symbol!,
          side: order.side!,
          type: order.type!,
          quantity: order.quantity!,
          price: order.price,
          requestId: `csv-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`
        }));
        
        const response = await orderManager.submitOrders(submitOrders);
        
        if (response.success) {
          const successCount = response.results.filter(r => r.success).length;
          const failCount = response.results.length - successCount;
          
          if (successCount > 0) {
            addToast('success', `Successfully submitted ${successCount} orders`);
          }
          
          if (failCount > 0) {
            addToast('warning', `Failed to submit ${failCount} orders`);
            
            // Log first few failures
            response.results.forEach((result, index) => {
              if (!result.success && index < 5) {
                addToast('error', `Order #${index + 1} failed: ${result.errorMessage || 'Unknown error'}`);
              }
            });
            
            if (failCount > 5) {
              addToast('info', `${failCount - 5} more order failures not shown`);
            }
          }
          
          // Clear state if all orders were successful
          if (failCount === 0) {
            setFile(null);
            setOrders([]);
            if (fileInputRef.current) {
              fileInputRef.current.value = '';
            }
          }
        } else {
          addToast('error', `Failed to submit orders: ${response.errorMessage || 'Unknown error'}`);
        }
      } else {
        // CANCEL operation
        addToast('info', `Cancelling ${orders.length} orders...`);
        
        const orderIds = orders.map(o => o.orderId!);
        const response = await orderManager.cancelOrders(orderIds);
        
        if (response.success) {
          const successCount = response.results.filter(r => r.success).length;
          const failCount = response.results.length - successCount;
          
          if (successCount > 0) {
            addToast('success', `Successfully cancelled ${successCount} orders`);
          }
          
          if (failCount > 0) {
            addToast('warning', `Failed to cancel ${failCount} orders`);
            
            // Log first few failures
            response.results.forEach((result, index) => {
              if (!result.success && index < 5) {
                addToast('error', `Cancel #${index + 1} failed: ${result.errorMessage || 'Unknown error'}`);
              }
            });
            
            if (failCount > 5) {
              addToast('info', `${failCount - 5} more cancellation failures not shown`);
            }
          }
          
          // Clear state if all cancellations were successful
          if (failCount === 0) {
            setFile(null);
            setOrders([]);
            if (fileInputRef.current) {
              fileInputRef.current.value = '';
            }
          }
        } else {
          addToast('error', `Failed to cancel orders: ${response.errorMessage || 'Unknown error'}`);
        }
      }
    } catch (error: any) {
      addToast('error', `Error processing request: ${error.message || 'Unknown error'}`);
    } finally {
      setIsSubmitting(false);
    }
  }, [operation, orders, isSubmitting, orderManager, addToast]);

  const handleClear = useCallback(() => {
    setFile(null);
    setOrders([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const getSampleFormat = () => {
    if (operation === 'SUBMIT') {
      return 'symbol,side,type,quantity,price\nAAPL,BUY,LIMIT,10,150.50\nMSFT,SELL,MARKET,5,';
    } else {
      return 'orderId\norder-123456\norder-789012';
    }
  };

  return (
    <div className="csv-order-upload">
      <div className="operation-toggle">
        <button 
          className={`toggle-button ${operation === 'SUBMIT' ? 'active' : ''}`} 
          onClick={() => handleOperationChange('SUBMIT')}
        >
          Submit Orders
        </button>
        <button 
          className={`toggle-button ${operation === 'CANCEL' ? 'active' : ''}`} 
          onClick={() => handleOperationChange('CANCEL')}
        >
          Cancel Orders
        </button>
      </div>
      
      <div 
        className={`drop-area ${isDragging ? 'dragging' : ''}`}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileInputChange}
          accept=".csv"
          className="file-input"
        />
        
        {file ? (
          <div className="file-info">
            <p className="file-name">{file.name}</p>
            <p className="file-stats">
              {orders.length} {operation === 'SUBMIT' ? 'orders' : 'cancellations'} loaded
            </p>
          </div>
        ) : (
          <div className="drop-message">
            <p>Drop {operation === 'SUBMIT' ? 'orders' : 'cancels'} CSV file here</p>
            <p>or</p>
            <button 
              type="button" 
              onClick={handleBrowseClick}
              className="browse-button"
            >
              Browse Files
            </button>
          </div>
        )}
      </div>
      
      {orders.length > 0 && (
        <div className="preview">
          <div className="preview-header">
            <span>Preview: {orders.length} {operation === 'SUBMIT' ? 'orders' : 'cancellations'}</span>
            {operation === 'SUBMIT' && (
              <span className="order-stats">
                {orders.filter(o => o.side === 'BUY').length} BUY | {orders.filter(o => o.side === 'SELL').length} SELL
              </span>
            )}
          </div>
          
          <div className="action-buttons">
            <button 
              onClick={handleClear}
              disabled={isSubmitting}
              className="clear-button"
            >
              Clear
            </button>
            
            <button 
              onClick={handleSubmit}
              disabled={isSubmitting || orders.length === 0}
              className="submit-button"
            >
              {isSubmitting 
                ? 'Processing...' 
                : operation === 'SUBMIT' 
                  ? `Submit ${orders.length} Orders` 
                  : `Cancel ${orders.length} Orders`}
            </button>
          </div>
        </div>
      )}
      
      <div className="format-info">
        <div className="format-header">
          <span>Expected CSV Format:</span>
        </div>
        <code className="format-example">{getSampleFormat()}</code>
      </div>
    </div>
  );
};

export default CsvOrderUpload;