// src/components/Common/ConnectionRecoveryDialog.tsx

import React, { useEffect, useState } from 'react';
import './ConnectionRecoveryDialog.css';
import { useConnection } from '../../contexts/ConnectionContext';

interface ConnectionRecoveryDialogProps {
  maxAttempts?: number;
}

const ConnectionRecoveryDialog: React.FC<ConnectionRecoveryDialogProps> = ({ 
  maxAttempts = 5 
}) => {
  const { 
    isConnected, 
    isRecovering, 
    recoveryAttempt, 
    manualReconnect 
  } = useConnection();
  
  const [visible, setVisible] = useState(false);
  
  // Show dialog when multiple recovery attempts fail
  useEffect(() => {
    if (!isConnected && recoveryAttempt >= 3 && !isRecovering) {
      setVisible(true);
    } else if (isConnected) {
      setVisible(false);
    }
  }, [isConnected, isRecovering, recoveryAttempt]);
  
  // Handle retry button click
  const handleRetry = async () => {
    await manualReconnect();
  };
  
  // Handle reload button click
  const handleReload = () => {
    window.location.reload();
  };
  
  if (!visible) {
    return null;
  }
  
  return (
    <div className="recovery-dialog-overlay">
      <div className="recovery-dialog">
        <div className="recovery-dialog-header">
          <h2>Connection Lost</h2>
        </div>
        <div className="recovery-dialog-content">
          <p>We're having trouble connecting to the trading servers.</p>
          <p>This could be due to:</p>
          <ul>
            <li>Network connectivity issues</li>
            <li>Server maintenance</li>
            <li>Your internet connection</li>
          </ul>
        </div>
        <div className="recovery-dialog-footer">
          <button 
            className="retry-button"
            onClick={handleRetry}
            disabled={isRecovering}
          >
            {isRecovering ? 'Reconnecting...' : 'Retry Connection'}
          </button>
          <button 
            className="reload-button"
            onClick={handleReload}
          >
            Reload Page
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConnectionRecoveryDialog;