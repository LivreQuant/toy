// src/components/Simulator/OrderSubmissionContainer.tsx
import React, { useState, useCallback } from 'react';
import CsvOrderUpload from './CsvOrderUpload';
import FingerprintUpload from './FingerprintUpload';
import './OrderSubmissionContainer.css';

type SubmissionMode = 'FILES' | 'FINGERPRINTS';

const OrderSubmissionContainer: React.FC = () => {
  const [submissionMode, setSubmissionMode] = useState<SubmissionMode>('FILES');

  const handleModeChange = useCallback((newMode: SubmissionMode) => {
    setSubmissionMode(newMode);
  }, []);

  return (
    <div className="order-submission-container">
      <div className="submission-mode-selector">
        <div className="mode-selector-header">
          <h3>Submission Method</h3>
          <p>Choose how you want to submit your convictions</p>
        </div>
        
        <div className="mode-toggle">
          <button 
            className={`mode-button ${submissionMode === 'FILES' ? 'active' : ''}`} 
            onClick={() => handleModeChange('FILES')}
          >
            <div className="mode-content">
              <span className="mode-icon">📁</span>
              <span className="mode-title">File Upload</span>
              <span className="mode-description">Upload CSV and research files directly</span>
            </div>
          </button>
          
          <button 
            className={`mode-button ${submissionMode === 'FINGERPRINTS' ? 'active' : ''}`} 
            onClick={() => handleModeChange('FINGERPRINTS')}
          >
            <div className="mode-content">
              <span className="mode-icon">🔒</span>
              <span className="mode-title">Fingerprint Submission</span>
              <span className="mode-description">Submit encoded file fingerprints for verification</span>
            </div>
          </button>
        </div>
      </div>

      <div className="submission-content">
        {submissionMode === 'FILES' ? (
          <CsvOrderUpload />
        ) : (
          <FingerprintUpload />
        )}
      </div>
    </div>
  );
};

export default OrderSubmissionContainer;