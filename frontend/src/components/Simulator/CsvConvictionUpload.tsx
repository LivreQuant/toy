// src/components/Simulator/CsvConvictionUpload.tsx
import React, { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useToast } from '../../hooks/useToast';
import { useConvictionManager } from '../../contexts/ConvictionContext';
import { useBookManager } from '../../hooks/useBookManager';
import { ConvictionModelConfig, ConvictionData } from '../../types'; // Add ConvictionData import
import FileUploadZone from './FileUploadZone';
import NotesInput from './NotesInput';
import ConvictionFileProcessor from './ConvictionFileProcessor';
import './CsvConvictionUpload.css';

// Operation types
type Operation = 'SUBMIT' | 'CANCEL';

interface SubmissionData {
  bookId: string;
  convictions: ConvictionData[];
  researchFile?: File;
  notes: string;
}

interface CancelData {
  bookId: string;
  convictionIds: [string];
  researchFile?: File;
  notes: string;
}

const CsvConvictionUpload: React.FC = () => {
  const { bookId } = useParams<{ bookId?: string }>();
  const { addToast } = useToast();
  const convictionManager = useConvictionManager();
  const bookManager = useBookManager();

  // State
  const [operation, setOperation] = useState<Operation>('SUBMIT');
  const [convictionFile, setConvictionFile] = useState<File | null>(null);
  const [researchFile, setResearchFile] = useState<File | null>(null);
  const [notes, setNotes] = useState('');
  const [convictions, setConvictions] = useState<ConvictionData[]>([]);
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

  // Process conviction file when it changes
  useEffect(() => {
    if (!convictionFile) {
      setConvictions([]);
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      const processor = new ConvictionFileProcessor(convictionSchema, addToast);
      
      let parsedConvictions: ConvictionData[];
      if (operation === 'SUBMIT') {
        parsedConvictions = processor.processSubmitCsv(content);
      } else {
        parsedConvictions = processor.processCancelCsv(content);
      }
      
      // Filter out convictions that don't have required fields for the API
      const validConvictions = parsedConvictions.filter(conviction => {
        if (operation === 'SUBMIT') {
          return conviction.instrumentId && conviction.convictionId;
        } else {
          return conviction.convictionId;
        }
      });
      
      setConvictions(validConvictions);
      
      if (validConvictions.length > 0) {
        addToast('success', `Loaded ${validConvictions.length} ${operation === 'SUBMIT' ? 'convictions' : 'cancellations'} from CSV`);
      } else {
        addToast('warning', `No valid ${operation === 'SUBMIT' ? 'convictions' : 'cancellations'} found in CSV`);
      }
    };
    
    reader.readAsText(convictionFile);
  }, [convictionFile, operation, convictionSchema, addToast]);

  const handleOperationChange = useCallback((newOperation: Operation) => {
    if (operation !== newOperation) {
      setOperation(newOperation);
      setConvictionFile(null);
      setResearchFile(null);
      setNotes('');
      setConvictions([]);
    }
  }, [operation]);

  const handleSubmit = useCallback(async () => {
    if (convictions.length === 0 || isSubmitting) return;
  
    if (!convictionFile) {
      addToast('error', 'Conviction file is required');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      if (operation === 'SUBMIT') {
        const hasResearch = researchFile ? 'with research' : '';
        const hasNotes = notes.trim() ? 'and notes' : '';
        const submitMessage = `Submitting ${convictions.length} convictions ${hasResearch} ${hasNotes}`.trim();
        
        addToast('info', submitMessage);
        
        // Convert ConvictionData to API format, filtering out invalid convictions
        const submitConvictions = convictions
          .filter((conviction): conviction is ConvictionData => 
            !!conviction.instrumentId && !!conviction.convictionId
          )
          .map(conviction => ({
            instrumentId: conviction.instrumentId,
            convictionId: conviction.convictionId,
            side: conviction.side,
            quantity: conviction.quantity,
            score: conviction.score,
            zscore: conviction.zscore,
            targetPercent: conviction.targetPercent,
            targetNotional: conviction.targetNotional,
            participationRate: conviction.participationRate,
            tag: conviction.tag,
            // Include multi-horizon zscores
            ...Object.keys(conviction).reduce((acc, key) => {
              if (key.startsWith('z') && (key.includes('min') || key.includes('hour') || key.includes('day') || key.includes('week'))) {
                acc[key] = conviction[key];
              }
              return acc;
            }, {} as Record<string, any>)
          }));

        if (submitConvictions.length === 0) {
          addToast('error', 'No valid convictions found. Please check that all convictions have instrumentId and convictionId.');
          return;
        }
        
        try {
          const response = await convictionManager.submitConvictions({
            bookId: bookId!, // ADD THIS LINE
            convictions: submitConvictions,
            researchFile: researchFile || undefined,
            notes: notes.trim() || undefined
          });
          
          if (response.success) {
            const successCount = response.results.filter(r => r.success).length;
            const failCount = response.results.length - successCount;
            
            if (successCount > 0) {
              const successMessage = researchFile || notes.trim() ? 
                `Successfully submitted ${successCount} convictions with additional context` :
                `Successfully submitted ${successCount} convictions`;
              addToast('success', successMessage);
            }
            
            if (failCount > 0) {
              addToast('warning', `Failed to submit ${failCount} convictions`);
              
              response.results.forEach((result, index) => {
                if (!result.success && index < 5) {
                  addToast('error', `Conviction #${index + 1} failed: ${result.errorMessage || 'Unknown error'}`);
                }
              });
              
              if (failCount > 5) {
                addToast('info', `${failCount - 5} more conviction failures not shown`);
              }
            }
            
            // Clear form on successful submission
            if (failCount === 0) {
              setConvictionFile(null);
              setResearchFile(null);
              setNotes('');
              setConvictions([]);
            }
          } else {
            addToast('error', `Failed to submit convictions: ${response.errorMessage || 'Unknown error'}`);
          }
        } catch (err: any) {
          addToast('error', `Error submitting convictions: ${err.message}`);
          console.error('Conviction submission error:', err);
        }
      } else {
        // CANCEL operation
        const hasNotes = notes.trim() ? 'with notes' : '';
        const hasResearch = researchFile ? 'and research' : '';
        addToast('info', `Cancelling ${convictions.length} convictions ${hasResearch} ${hasNotes}`.trim());
        
        const convictionIds = convictions
          .filter(conviction => !!conviction.convictionId)
          .map(o => o.convictionId!);

        if (convictionIds.length === 0) {
          addToast('error', 'No valid conviction IDs found for cancellation.');
          return;
        }
        
        try {
          const response = await convictionManager.cancelConvictions({
            bookId: bookId!, // ADD THIS LINE
            convictionIds: convictionIds,
            researchFile: researchFile || undefined,
            notes: notes.trim() || undefined
          });
          
          if (response.success) {
            const successCount = response.results.filter(r => r.success).length;
            const failCount = response.results.length - successCount;
            
            if (successCount > 0) {
              const successMessage = researchFile || notes.trim() ? 
                `Successfully cancelled ${successCount} convictions with additional context` :
                `Successfully cancelled ${successCount} convictions`;
              addToast('success', successMessage);
            }
            
            if (failCount > 0) {
              addToast('warning', `Failed to cancel ${failCount} convictions`);
              
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
              setConvictionFile(null);
              setResearchFile(null);
              setNotes('');
              setConvictions([]);
            }
          } else {
            addToast('error', `Failed to cancel convictions: ${response.errorMessage || 'Unknown error'}`);
          }
        } catch (err: any) {
          addToast('error', `Error cancelling convictions: ${err.message}`);
          console.error('Conviction cancellation error:', err);
        }
      }
    } catch (error: any) {
      addToast('error', `Error processing request: ${error.message || 'Unknown error'}`);
      console.error('Request error:', error);
    } finally {
      setIsSubmitting(false);
    }
  }, [operation, convictions, convictionFile, researchFile, notes, isSubmitting, convictionManager, addToast]);

  const handleClear = useCallback(() => {
    setConvictionFile(null);
    setResearchFile(null);
    setNotes('');
    setConvictions([]);
  }, []);

  const getSampleFormat = useCallback(() => {
    if (operation === 'CANCEL') {
      return `
convictionId
conviction-001
conviction-002`;
    }

    // Use ConvictionFileProcessor to get the sample format
    const processor = new ConvictionFileProcessor(convictionSchema, addToast);
    return processor.getSampleFormat();
  }, [operation, convictionSchema, addToast]);

  if (isLoadingSchema) {
    return (
      <div className="csv-conviction-upload">
        <div style={{ textAlign: 'center', padding: '20px' }}>
          Loading book schema...
        </div>
      </div>
    );
  }

  return (
    <div className="csv-conviction-upload">
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
          onFileSelect={setConvictionFile}
          file={convictionFile}
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
      
      {convictions.length > 0 && (
        <div className="preview">
          <div className="preview-header">
            <span>Preview: {convictions.length} {operation === 'SUBMIT' ? 'convictions' : 'cancellations'}</span>
            {operation === 'SUBMIT' && (
              <span className="conviction-stats">
                {convictions.filter(o => o.side === 'BUY').length} BUY | {convictions.filter(o => o.side === 'SELL').length} SELL
              </span>
            )}
          </div>
          
          <div className="submission-summary">
            <div className="summary-item">
              <strong>Conviction File:</strong> {convictionFile?.name} ({convictions.length} {operation === 'SUBMIT' ? 'convictions' : 'cancellations'})
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
              disabled={isSubmitting || convictions.length === 0 || !convictionFile}
              className={`submit-button ${isSubmitting ? 'processing' : ''}`}
            >
              {isSubmitting 
                ? 'Processing... Do Not Refresh' 
                : operation === 'SUBMIT' 
                  ? `Submit ${convictions.length} Convictions` 
                  : `Cancel ${convictions.length} Convictions`}
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

export default CsvConvictionUpload;