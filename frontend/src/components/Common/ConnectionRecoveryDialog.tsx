// src/components/Common/ConnectionRecoveryDialog.tsx
import React, { useEffect, useState } from 'react';
import './ConnectionRecoveryDialog.css';
import { useConnection } from '../../contexts/ConnectionContext';
import { useToast } from '../../contexts/ToastContext';

interface ConnectionRecoveryDialogProps {
  maxAttempts?: number;
}

const ConnectionRecoveryDialog: React.FC<ConnectionRecoveryDialogProps> = () => {
  const { 
    isConnected, 
    isRecovering, 
    recoveryAttempt, 
    manualReconnect,
    connectionState
  } = useConnection();
  const { addToast } = useToast();
  
  const [visible, setVisible] = useState(false);
  
  // Show dialog when multiple recovery attempts fail
  useEffect(() => {
    if (!isConnected && recoveryAttempt >= 3 && !isRecovering) {
      setVisible(true);
    } else if (isConnected) {
      setVisible(false);
    }
  }, [isConnected, isRecovering, recoveryAttempt]);
  
  // Handle manual reconnection with toast feedback
  const handleManualReconnect = async () => {
    try {
      const success = await manualReconnect();
      
      if (success) {
        addToast({
          type: 'success',
          message: 'Successfully reconnected to trading servers',
          duration: 5000
        });
      } else {
        addToast({
          type: 'error',
          message: 'Failed to reconnect. Please check your network.',
          duration: 7000
        });
      }
    } catch (error) {
      addToast({
        type: 'error',
        message: 'An unexpected error occurred during reconnection',
        duration: 7000
      });
    }
  };

  // Get connection errors from unified state
  const getConnectionErrors = () => {
    const errors = [];
    
    if (connectionState?.webSocketState?.error) {
      errors.push(`WebSocket: ${connectionState.webSocketState.error}`);
    }
    
    if (connectionState?.sseState?.error) {
      errors.push(`Data Stream: ${connectionState.sseState.error}`);
    }
    
    return errors.length > 0 ? errors : ['Connection interrupted - reason unknown'];
  };

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
          
          {/* Show specific errors if available */}
          {getConnectionErrors().length > 0 && (
            <div className="error-details">
              <p>Error details:</p>
              <ul>
                {getConnectionErrors().map((error, index) => (
                  <li key={index}>{error}</li>
                ))}
              </ul>
            </div>
          )}
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