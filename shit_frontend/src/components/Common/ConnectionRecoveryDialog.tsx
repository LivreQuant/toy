// src/components/Common/ConnectionRecoveryDialog.tsx
import React from 'react';
import { useConnectionState, useConnectionActions } from '../../contexts/ConnectionContext';
import { useAuthState } from '../../hooks/useAppState';
import { ConnectionStatus } from '../../services/connection/unified-connection-state';
import './ConnectionRecoveryDialog.css';

const ConnectionRecoveryDialog: React.FC = () => {
  // Get authentication state using reactive state hook
  const authState = useAuthState();
  
  // Get connection state using reactive state hook
  const connectionState = useConnectionState();
  
  // Get connection actions from context
  const { manualReconnect } = useConnectionActions();

  // Only show dialog if:
  // 1. User is authenticated and auth check completed
  // 2. Connection is explicitly disconnected
  // 3. Not already connecting or recovering
  const showDialog = !authState.isLoading && 
                     authState.isAuthenticated && 
                     connectionState.status === ConnectionStatus.DISCONNECTED && 
                     !connectionState.isConnecting && 
                     !connectionState.isRecovering;

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
          {connectionState.recoveryAttempt > 0 && (
            <p>Attempted to reconnect {connectionState.recoveryAttempt} times automatically.</p>
          )}
          <p>You can try reconnecting manually or reload the application.</p>
        </div>
        <div className="recovery-dialog-footer">
           <button className="reload-button" onClick={handleReload}>Reload App</button>
           <button
              className="retry-button"
              onClick={handleRetry}
              disabled={connectionState.isConnecting || connectionState.isRecovering}
           >
              Retry Connection
           </button>
        </div>
      </div>
    </div>
  );
};

export default ConnectionRecoveryDialog;