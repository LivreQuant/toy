// src/components/Simulator/CsvOrderUpload.tsx
import React, { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useToast } from '../../hooks/useToast';
import { useOrderManager } from '../../contexts/OrderContext';
import { useBookManager } from '../../hooks/useBookManager';
import { ConvictionModelConfig } from '../../types';
import FileUploadZone from './FileUploadZone';
import NotesInput from './NotesInput';
import OrderFileProcessor from './OrderFileProcessor';
import { OrderData } from '../../types';
import './CsvOrderUpload.css';

// Operation types
type Operation = 'SUBMIT' | 'CANCEL';

interface SubmissionData {
  orders: OrderData[];
  researchFile?: File;
  notes: string;
}

interface CancelData {
  orderIds: [string];
  researchFile?: File;
  notes: string;
}

const CsvOrderUpload: React.FC = () => {
  const { bookId } = useParams<{ bookId?: string }>();
  const { addToast } = useToast();
  const orderManager = useOrderManager();
  const bookManager = useBookManager();

  // State
  const [operation, setOperation] = useState<Operation>('SUBMIT');
  const [orderFile, setOrderFile] = useState<File | null>(null);
  const [researchFile, setResearchFile] = useState<File | null>(null);
  const [notes, setNotes] = useState('');
  const [orders, setOrders] = useState<OrderData[]>([]);
  const [convictionSchema, setConvictionSchema] = useState<ConvictionModelConfig | null>(null);
  const [isLoadingSchema, setIsLoadingSchema] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Load the book's conviction schema
  useEffect(() => {
    const loadBookSchema = async () => {
      if (!bookId) return;
      
      setIsLoadingSchema(true);
      try {
        const response = await bookManager.fetchBook(bookId);
        
        if (response.success && response.book?.convictionSchema) {
          setConvictionSchema(response.book.convictionSchema);
        }
      } catch (error: any) {
        console.error('Error loading book schema:', error);
        addToast('warning', 'Could not load book schema, using default validation');
      } finally {
        setIsLoadingSchema(false);
      }
    };

    loadBookSchema();
  }, [bookId, bookManager, addToast]);

  // Process order file when it changes
  useEffect(() => {
    if (!orderFile) {
      setOrders([]);
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      const processor = new OrderFileProcessor(convictionSchema, addToast);
      
      let parsedOrders: OrderData[];
      if (operation === 'SUBMIT') {
        parsedOrders = processor.processSubmitCsv(content);
      } else {
        parsedOrders = processor.processCancelCsv(content);
      }
      
      setOrders(parsedOrders);
      
      if (parsedOrders.length > 0) {
        addToast('success', `Loaded ${parsedOrders.length} ${operation === 'SUBMIT' ? 'orders' : 'cancellations'} from CSV`);
      } else {
        addToast('warning', `No valid ${operation === 'SUBMIT' ? 'orders' : 'cancellations'} found in CSV`);
      }
    };
    
    reader.readAsText(orderFile);
  }, [orderFile, operation, convictionSchema, addToast]);

  const handleOperationChange = useCallback((newOperation: Operation) => {
    if (operation !== newOperation) {
      setOperation(newOperation);
      setOrderFile(null);
      setResearchFile(null);
      setNotes('');
      setOrders([]);
    }
  }, [operation]);

  const handleSubmit = useCallback(async () => {
    if (orders.length === 0 || isSubmitting) return;
  
    if (!orderFile) {
      addToast('error', 'Order file is required');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      if (operation === 'SUBMIT') {
        const hasResearch = researchFile ? 'with research' : '';
        const hasNotes = notes.trim() ? 'and notes' : '';
        const submitMessage = `Submitting ${orders.length} orders ${hasResearch} ${hasNotes}`.trim();
        
        addToast('info', submitMessage);
        
        // Convert OrderData to OrderRequest format
        const submitOrders = orders.map(order => ({
          instrumentId: order.instrumentId!,
          orderId: order.orderId!,
          side: order.side,
          quantity: order.quantity,
          score: order.score,
          zscore: order.zscore,
          targetPercent: order.targetPercent,
          targetNotional: order.targetNotional,
          participationRate: order.participationRate,
          tag: order.tag,
          // Include multi-horizon zscores
          ...Object.keys(order).reduce((acc, key) => {
            if (key.startsWith('z') && (key.includes('min') || key.includes('hour') || key.includes('day') || key.includes('week'))) {
              acc[key] = order[key];
            }
            return acc;
          }, {} as Record<string, any>)
        }));
        
        try {
          const response = await orderManager.submitOrders({
            orders: submitOrders,
            researchFile: researchFile || undefined,
            notes: notes.trim() || undefined
          });
          
          if (response.success) {
            const successCount = response.results.filter(r => r.success).length;
            const failCount = response.results.length - successCount;
            
            if (successCount > 0) {
              const successMessage = researchFile || notes.trim() ? 
                `Successfully submitted ${successCount} orders with additional context` :
                `Successfully submitted ${successCount} orders`;
              addToast('success', successMessage);
            }
            
            if (failCount > 0) {
              addToast('warning', `Failed to submit ${failCount} orders`);
              
              response.results.forEach((result, index) => {
                if (!result.success && index < 5) {
                  addToast('error', `Order #${index + 1} failed: ${result.errorMessage || 'Unknown error'}`);
                }
              });
              
              if (failCount > 5) {
                addToast('info', `${failCount - 5} more order failures not shown`);
              }
            }
            
            // Clear form on successful submission
            if (failCount === 0) {
              setOrderFile(null);
              setResearchFile(null);
              setNotes('');
              setOrders([]);
            }
          } else {
            addToast('error', `Failed to submit convictions: ${response.errorMessage || 'Unknown error'}`);
          }
        } catch (err: any) {
          addToast('error', `Error submitting orders: ${err.message}`);
          console.error('Order submission error:', err);
        }
      } else {
        // CANCEL operation
        const hasNotes = notes.trim() ? 'with notes' : '';
        const hasResearch = researchFile ? 'and research' : '';
        addToast('info', `Cancelling ${orders.length} orders ${hasResearch} ${hasNotes}`.trim());
        
        const orderIds = orders.map(o => o.orderId!);
        
        try {
          const response = await orderManager.cancelOrders({
            orderIds: orderIds,
            researchFile: researchFile || undefined,
            notes: notes.trim() || undefined
          });
          
          if (response.success) {
            const successCount = response.results.filter(r => r.success).length;
            const failCount = response.results.length - successCount;
            
            if (successCount > 0) {
              const successMessage = researchFile || notes.trim() ? 
                `Successfully cancelled ${successCount} orders with additional context` :
                `Successfully cancelled ${successCount} orders`;
              addToast('success', successMessage);
            }
            
            if (failCount > 0) {
              addToast('warning', `Failed to cancel ${failCount} orders`);
              
              response.results.forEach((result, index) => {
                if (!result.success && index < 5) {
                  addToast('error', `Cancel #${index + 1} failed: ${result.errorMessage || 'Unknown error'}`);
                }
              });
              
              if (failCount > 5) {
                addToast('info', `${failCount - 5} more cancellation failures not shown`);
              }
            }
            
            // Clear form on successful submission
            if (failCount === 0) {
              setOrderFile(null);
              setResearchFile(null);
              setNotes('');
              setOrders([]);
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
  }, [operation, orders, orderFile, researchFile, notes, isSubmitting, orderManager, addToast]);

  const handleClear = useCallback(() => {
    setOrderFile(null);
    setResearchFile(null);
    setNotes('');
    setOrders([]);
  }, []);

  const getSampleFormat = useCallback(() => {
    if (operation === 'CANCEL') {
      return `
orderId
order-001
order-002`;
    }

    // Use OrderFileProcessor to get the sample format
    const processor = new OrderFileProcessor(convictionSchema, addToast);
    return processor.getSampleFormat();
  }, [operation, convictionSchema, addToast]);

  if (isLoadingSchema) {
    return (
      <div className="csv-order-upload">
        <div style={{ textAlign: 'center', padding: '20px' }}>
          Loading book schema...
        </div>
      </div>
    );
  }

  return (
    <div className="csv-order-upload">
      <div className="operation-toggle">
        <button 
          className={`toggle-button ${operation === 'SUBMIT' ? 'active' : ''}`} 
          onClick={() => handleOperationChange('SUBMIT')}
        >
          Submit Convictions
        </button>
        <button 
          className={`toggle-button ${operation === 'CANCEL' ? 'active' : ''}`} 
          onClick={() => handleOperationChange('CANCEL')}
        >
          Cancel Convictions
        </button>
      </div>

      <div className="upload-section">
        <FileUploadZone
          title="Conviction File"
          acceptedTypes=".csv"
          onFileSelect={setOrderFile}
          file={orderFile}
          required={true}
          description={operation === 'SUBMIT' ? 'CSV file containing your convictions' : 'CSV file containing conviction IDs to cancel'}
        />

        <FileUploadZone
          title="Research File"
          acceptedTypes=".pdf,.doc,.docx,.txt,.md"
          onFileSelect={setResearchFile}
          file={researchFile}
          required={false}
          description="Optional research document supporting your decisions"
        />

        <NotesInput
          value={notes}
          onChange={setNotes}
          required={false}
          placeholder={operation === 'SUBMIT' ? 
            "Optional: Explain your trading thesis, risk considerations, and rationale..." : 
            "Optional: Explain why you're cancelling these convictions..."}
        />
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
          
          <div className="submission-summary">
            <div className="summary-item">
              <strong>Order File:</strong> {orderFile?.name} ({orders.length} {operation === 'SUBMIT' ? 'orders' : 'cancellations'})
            </div>
            {researchFile && (
              <div className="summary-item">
                <strong>Research File:</strong> {researchFile.name} ({(researchFile.size / 1024).toFixed(1)} KB)
              </div>
            )}
            {notes.trim() && (
              <div className="summary-item">
                <strong>Notes:</strong> {notes.length > 100 ? `${notes.substring(0, 100)}...` : notes}
              </div>
            )}
            {!researchFile && !notes.trim() && (
              <div className="summary-item" style={{ color: '#666', fontStyle: 'italic' }}>
                No additional context provided
              </div>
            )}
          </div>
          
          <div className="action-buttons">
            <button 
              onClick={handleClear}
              disabled={isSubmitting}
              className="clear-button"
            >
              Clear All
            </button>
            
            <button 
              onClick={handleSubmit}
              disabled={isSubmitting || orders.length === 0 || !orderFile}
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
          <span>Expected CSV Conviction Format:</span>
          {convictionSchema && (
            <small style={{ display: 'block', marginTop: '4px', color: '#666' }}>
              Based on book's conviction model: {convictionSchema.portfolioApproach} / {
                convictionSchema.portfolioApproach === 'target' 
                  ? convictionSchema.targetConvictionMethod 
                  : convictionSchema.incrementalConvictionMethod
              }
            </small>
          )}
        </div>
        <code className="format-example">{getSampleFormat()}</code>
      </div>
    </div>
  );
};

export default CsvOrderUpload;