// src/components/Common/ConnectionRecoveryDialog.tsx
import React from 'react';
import { useConnection } from '../../contexts/ConnectionContext';
import { useAuth } from '../../contexts/AuthContext';
import { ConnectionStatus } from '../../services/connection/unified-connection-state';
import './ConnectionRecoveryDialog.css';

const ConnectionRecoveryDialog: React.FC = () => {
  // Get authentication state
  const { isAuthenticated, isLoading } = useAuth();
  
  // Get connection state
  const {
    isConnected,
    isConnecting,
    isRecovering,
    recoveryAttempt,
    manualReconnect,
    overallStatus
  } = useConnection();

  // Only show dialog if:
  // 1. User is authenticated and auth check completed
  // 2. Connection is explicitly disconnected
  // 3. Not already connecting or recovering
  const showDialog = !isLoading && 
                     isAuthenticated && 
                     overallStatus === ConnectionStatus.DISCONNECTED && 
                     !isConnecting && 
                     !isRecovering;

  if (!showDialog) {
    return null;
  }

  const handleRetry = () => {
    manualReconnect();
  };

  const handleReload = () => {
    window.location.reload();
  }

  return (
    <div className="recovery-dialog-overlay">
      <div className="recovery-dialog">
        <div className="recovery-dialog-header">
          <h2>Connection Lost</h2>
        </div>
        <div className="recovery-dialog-content">
          <p>Connection to the server was lost.</p>
          {recoveryAttempt > 0 && <p>Attempted to reconnect {recoveryAttempt} times automatically.</p>}
          <p>You can try reconnecting manually or reload the application.</p>
        </div>
        <div className="recovery-dialog-footer">
           <button className="reload-button" onClick={handleReload}>Reload App</button>
           <button
              className="retry-button"
              onClick={handleRetry}
              disabled={isConnecting || isRecovering}
           >
              Retry Connection
           </button>
        </div>
      </div>
    </div>
  );
};

export default ConnectionRecoveryDialog;