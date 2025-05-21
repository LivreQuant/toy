// src/components/Simulator/CsvOrderUpload.tsx
import React, { useState, useCallback, useRef } from 'react';
import { useToast } from '../../hooks/useToast';
import { useOrderManager } from '../../contexts/OrderContext';
import { Order } from '../../types';
import './CsvOrderUpload.css';

// Operation types
type Operation = 'SUBMIT' | 'CANCEL';

interface OrderData {
  instrumentId?: string;
  orderId?: string;
  side?: 'BUY' | 'SELL' | 'CLOSE';
  quantity?: number;
  zscore?: number;
  participationRate?: 'LOW' | 'MEDIUM' | 'HIGH' | number;
  category?: string;
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
    
    // Required columns for any order submission
    const requiredColumns = ['instrumentid', 'orderid'];
    
    const missingColumns = requiredColumns.filter(col => !header.includes(col));
    
    if (missingColumns.length > 0) {
      addToast('error', `CSV is missing required columns: ${missingColumns.join(', ')}`);
      return [];
    }

    // Map column indices
    const columnMap: Record<string, number> = {};
    header.forEach((colName, index) => {
      columnMap[colName] = index;
    });

    // Process data rows
    const parsedOrders: OrderData[] = [];
    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) continue;
      
      const values = lines[i].split(',').map(val => val.trim());
      
      // Basic validation - ensure enough columns
      if (values.length < requiredColumns.length) {
        addToast('warning', `Skipping row ${i+1}: insufficient columns`);
        continue;
      }

      // Create order object with required fields
      const order: OrderData = {
        instrumentId: values[columnMap.instrumentid],
        orderId: values[columnMap.orderid]
      };
      
      // Add optional fields if they exist in the CSV
      
      // Side
      if ('side' in columnMap && values[columnMap.side]) {
        const side = values[columnMap.side].toUpperCase();
        if (['BUY', 'SELL', 'CLOSE'].includes(side)) {
          order.side = side as 'BUY' | 'SELL' | 'CLOSE';
        } else {
          addToast('warning', `Row ${i+1}: invalid side '${values[columnMap.side]}' (must be BUY, SELL, or CLOSE), ignoring`);
        }
      }
      
      // Quantity
      if ('quantity' in columnMap && values[columnMap.quantity]) {
        const quantity = parseFloat(values[columnMap.quantity]);
        if (!isNaN(quantity) && quantity > 0) {
          order.quantity = quantity;
        } else {
          addToast('warning', `Row ${i+1}: invalid quantity '${values[columnMap.quantity]}', ignoring`);
        }
      }
      
      // Z-score
      if ('zscore' in columnMap && values[columnMap.zscore]) {
        const zscore = parseFloat(values[columnMap.zscore]);
        if (!isNaN(zscore)) {
          order.zscore = zscore;
        } else {
          addToast('warning', `Row ${i+1}: invalid zscore '${values[columnMap.zscore]}', ignoring`);
        }
      }
      
      // Participation Rate
      if ('participationrate' in columnMap && values[columnMap.participationrate]) {
        const rateValue = values[columnMap.participationrate];
        // Try to parse as number first
        const numRate = parseFloat(rateValue);
        
        if (!isNaN(numRate)) {
          order.participationRate = numRate;
        } else {
          // Try as string enum
          const strRate = rateValue.toUpperCase();
          if (['LOW', 'MEDIUM', 'HIGH'].includes(strRate)) {
            order.participationRate = strRate as 'LOW' | 'MEDIUM' | 'HIGH';
          } else {
            addToast('warning', `Row ${i+1}: invalid participation rate '${rateValue}', ignoring`);
          }
        }
      }
      
      // Category
      if ('category' in columnMap) {
        order.category = values[columnMap.category];
      }

      // Validation checks - we need either side or zscore, and quantity
      if (!order.side && order.zscore === undefined) {
        addToast('warning', `Row ${i+1}: at least one of 'side' or 'zscore' is required, skipping order`);
        continue;
      }
      
      if (order.quantity === undefined) {
        addToast('warning', `Row ${i+1}: 'quantity' is required, skipping order`);
        continue;
      }

      parsedOrders.push(order);
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
        
        // Convert OrderData to Order format
        const submitOrders = orders.map(order => ({
          instrumentId: order.instrumentId!,
          orderId: order.orderId!,
          side: order.side,
          quantity: order.quantity,
          zscore: order.zscore,
          participationRate: order.participationRate,
          category: order.category
        }));
        
        try {
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
        } catch (err: any) {
          addToast('error', `Error submitting orders: ${err.message}`);
          console.error('Order submission error:', err);
        }
      } else {
        // CANCEL operation
        addToast('info', `Cancelling ${orders.length} orders...`);
        
        const orderIds = orders.map(o => o.orderId!);
        
        try {
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
        } catch (err: any) {
          addToast('error', `Error cancelling orders: ${err.message}`);
          console.error('Order cancellation error:', err);
        }
      }
    } catch (error: any) {
      addToast('error', `Error processing request: ${error.message || 'Unknown error'}`);
      console.error('Request error:', error);
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
      return `instrumentId,side,quantity,participationRate,category,orderId
AAPL.US,BUY,1000,HIGH,value,order-001
MSFT.US,SELL,500,MEDIUM,momentum,order-002
GOOG.US,BUY,200,0.25,technical,order-003`;
    } else {
      return `orderId
order-001
order-002`;
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
              className={`submit-button ${isSubmitting ? 'processing' : ''}`}
            >
              {isSubmitting 
                ? 'Processing... Do Not Refresh' 
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