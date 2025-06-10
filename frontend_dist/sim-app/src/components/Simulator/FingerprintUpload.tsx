// src/components/Simulator/FingerprintUpload.tsx
import React, { useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useToast } from '../../hooks/useToast';
import { useConvictionManager } from '../../contexts/ConvictionContext';
import { useBookManager } from '../../hooks/useBookManager';
import { ConvictionModelConfig } from '@trading-app/types-core';
import ConvictionFileProcessor from './ConvictionFileProcessor';
import './FingerprintUpload.css';

// Operation types
type Operation = 'SUBMIT' | 'CANCEL';

const FingerprintUpload: React.FC = () => {
  const { bookId } = useParams<{ bookId?: string }>();
  const { addToast } = useToast();
  const convictionManager = useConvictionManager();
  const bookManager = useBookManager();

  // State
  const [operation, setOperation] = useState<Operation>('SUBMIT');
  const [convictionFileFingerprint, setConvictionFileFingerprint] = useState('');
  const [researchFileFingerprint, setResearchFileFingerprint] = useState('');
  const [notes, setNotes] = useState('');
  const [convictionSchema, setConvictionSchema] = useState<ConvictionModelConfig | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Load the book's conviction schema
  React.useEffect(() => {
    const loadBookSchema = async () => {
      if (!bookId) return;
      
      try {
        const response = await bookManager.fetchBook(bookId);
        
        if (response.success && response.book?.convictionSchema) {
          setConvictionSchema(response.book.convictionSchema);
        }
      } catch (error: any) {
        console.error('Error loading book schema:', error);
        addToast('warning', 'Could not load book schema');
      }
    };

    loadBookSchema();
  }, [bookId, bookManager, addToast]);

  const handleOperationChange = useCallback((newOperation: Operation) => {
    if (operation !== newOperation) {
      setOperation(newOperation);
      setConvictionFileFingerprint('');
      setResearchFileFingerprint('');
      setNotes('');
    }
  }, [operation]);

  const validateFingerprint = (fingerprint: string): boolean => {
    // Basic validation for encoded fingerprint strings
    // You can adjust this regex based on your specific fingerprint format
    const fingerprintRegex = /^[A-Za-z0-9+/]+=*$/; // Base64 format
    return fingerprintRegex.test(fingerprint) && fingerprint.length >= 32;
  };
    
  const handleSubmit = useCallback(async () => {
    if (isSubmitting) return;

    // Validation
    if (!convictionFileFingerprint.trim()) {
      addToast('error', 'Conviction file fingerprint is required');
      return;
    }

    if (!validateFingerprint(convictionFileFingerprint)) {
      addToast('error', 'Invalid conviction file fingerprint format');
      return;
    }

    if (researchFileFingerprint && !validateFingerprint(researchFileFingerprint)) {
      addToast('error', 'Invalid research file fingerprint format');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      if (operation === 'SUBMIT') {
        const hasResearch = researchFileFingerprint ? 'with research fingerprint' : '';
        const hasNotes = notes.trim() ? 'and notes' : '';
        const submitMessage = `Submitting conviction fingerprint ${hasResearch} ${hasNotes}`.trim();
        
        addToast('info', submitMessage);
        
        try {
          const response = await convictionManager.submitConvictionsEncoded({
            bookId: bookId!, // ADD THIS LINE
            convictions: convictionFileFingerprint.trim(),
            researchFile: researchFileFingerprint.trim() || undefined,
            notes: notes.trim() || undefined
          });
          
          if (response.success) {
            addToast('success', 'Conviction fingerprint submitted successfully');
            
            // Clear form on successful submission
            setConvictionFileFingerprint('');
            setResearchFileFingerprint('');
            setNotes('');
          } else {
            addToast('error', `Failed to submit fingerprint: ${response.errorMessage || 'Unknown error'}`);
          }
        } catch (err: any) {
          addToast('error', `Error submitting fingerprint: ${err.message}`);
          console.error('Fingerprint submission error:', err);
        }
      } else {
        // CANCEL operation
        const hasResearch = researchFileFingerprint ? 'with research fingerprint' : '';
        const hasNotes = notes.trim() ? 'and notes' : '';
        addToast('info', `Submitting cancellation fingerprint ${hasResearch} ${hasNotes}`.trim());
        
        try {
          const response = await convictionManager.cancelConvictionsEncoded({
            bookId: bookId!, // ADD THIS LINE
            convictionIds: convictionFileFingerprint.trim(), // For cancel, the fingerprint contains conviction IDs
            researchFile: researchFileFingerprint.trim() || undefined,
            notes: notes.trim() || undefined
          });
          
          if (response.success) {
            addToast('success', 'Cancellation fingerprint submitted successfully');
            
            // Clear form on successful submission
            setConvictionFileFingerprint('');
            setResearchFileFingerprint('');
            setNotes('');
          } else {
            addToast('error', `Failed to submit cancellation fingerprint: ${response.errorMessage || 'Unknown error'}`);
          }
        } catch (err: any) {
          addToast('error', `Error submitting cancellation fingerprint: ${err.message}`);
          console.error('Cancellation fingerprint error:', err);
        }
      }
    } catch (error: any) {
      addToast('error', `Error processing request: ${error.message || 'Unknown error'}`);
      console.error('Request error:', error);
    } finally {
      setIsSubmitting(false);
    }
  }, [operation, convictionFileFingerprint, researchFileFingerprint, notes, isSubmitting, convictionManager, addToast]);

  const handleClear = useCallback(() => {
    setConvictionFileFingerprint('');
    setResearchFileFingerprint('');
    setNotes('');
  }, []);

  const getSampleFormat = useCallback(() => {
    if (operation === 'CANCEL') {
      return `convictionId
conviction-001
conviction-002`;
    }

    // Use ConvictionFileProcessor to get the sample format
    if (convictionSchema) {
      const processor = new ConvictionFileProcessor(convictionSchema, addToast);
      return processor.getSampleFormat();
    }
    
    return 'Loading schema...';
  }, [operation, convictionSchema, addToast]);

  return (
    <div className="fingerprint-upload">
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

      <div className="fingerprint-section">
        <div className="fingerprint-info">
          <h3>Fingerprint Submission</h3>
          <p>
            Submit your encoded conviction and research files. 
            This allows you to commit to your decisions without immediately revealing the file contents.
          </p>
        </div>

        <div className="fingerprint-input-group">
          <div className="fingerprint-input-container">
            <label htmlFor="conviction-fingerprint">
              Conviction File Fingerprint <span className="required">*</span>
            </label>
            <textarea
              id="conviction-fingerprint"
              className="fingerprint-input"
              value={convictionFileFingerprint}
              onChange={(e) => setConvictionFileFingerprint(e.target.value)}
              placeholder="Paste your encoded conviction file fingerprint here..."
              rows={4}
              required
            />
            {convictionFileFingerprint && !validateFingerprint(convictionFileFingerprint) && (
              <p className="error-message">Invalid fingerprint format</p>
            )}
          </div>

          <div className="fingerprint-input-container">
            <label htmlFor="research-fingerprint">
              Research File Fingerprint <span className="optional">(Optional)</span>
            </label>
            <textarea
              id="research-fingerprint"
              className="fingerprint-input"
              value={researchFileFingerprint}
              onChange={(e) => setResearchFileFingerprint(e.target.value)}
              placeholder="Paste your encoded research file fingerprint here..."
              rows={4}
            />
            {researchFileFingerprint && !validateFingerprint(researchFileFingerprint) && (
              <p className="error-message">Invalid fingerprint format</p>
            )}
          </div>

          <div className="fingerprint-input-container">
            <label htmlFor="notes">
              Notes <span className="optional">(Optional)</span>
            </label>
            <textarea
              id="notes"
              className="notes-input"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={operation === 'SUBMIT' ? 
                "Optional: Explain your trading thesis, risk considerations, and rationale..." : 
                "Optional: Explain why you're cancelling these convictions..."}
              rows={4}
              maxLength={1000}
            />
            <div className="character-count">
              {notes.length}/1000
            </div>
          </div>
        </div>

        <div className="fingerprint-actions">
          <button 
            onClick={handleClear}
            disabled={isSubmitting}
            className="clear-button"
          >
            Clear All
          </button>
          
          <button 
            onClick={handleSubmit}
            disabled={isSubmitting || !convictionFileFingerprint.trim() || !validateFingerprint(convictionFileFingerprint)}
            className={`submit-button ${isSubmitting ? 'processing' : ''}`}
          >
            {isSubmitting 
              ? 'Processing... Do Not Refresh' 
              : operation === 'SUBMIT' 
                ? 'Submit Fingerprint' 
                : 'Submit Cancellation Fingerprint'}
          </button>
        </div>
      </div>
      
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

export default FingerprintUpload;