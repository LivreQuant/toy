// src/components/Common/ConnectionStatus.tsx
import React from 'react';
import { useConnectionState, useAuthState } from '../../hooks/useAppState';
import './ConnectionStatus.css';

const ConnectionStatus: React.FC = () => {
  // Use reactive state hooks
  const connectionState = useConnectionState();
  const authState = useAuthState();

  // Don't show connection status if user is not authenticated or auth is still loading
  if (!authState.isAuthenticated || authState.isLoading) {
    return null;
  }

  // Determine the text and CSS class based on the connection status
  const getStatusDisplay = () => {
    switch (connectionState.status) {
      case 'CONNECTED':
        return { text: `Connected (${connectionState.quality})`, className: connectionState.quality.toLowerCase() };
      case 'CONNECTING':
        return { text: 'Connecting...', className: 'connecting' };
      case 'RECOVERING':
        return { text: `Reconnecting (Attempt ${connectionState.recoveryAttempt})...`, className: 'recovering' };
      case 'DISCONNECTED':
        return { text: 'Disconnected', className: 'disconnected' };
      default:
        return { text: 'Unknown', className: 'unknown' };
    }
  };

  const { text: statusText, className: statusClass } = getStatusDisplay();

  return (
    <div className={`connection-indicator ${statusClass}`}>
      <div className="indicator-text">
        <span className="status-text">{statusText}</span>
        <span className={`simulator-status`}>
          Simulator: {connectionState.simulatorStatus || 'N/A'}
        </span>
      </div>
      
      {/* Show spinner and attempt count when recovering */}
      {connectionState.isRecovering && (
        <div className="recovery-progress" title={`Attempt ${connectionState.recoveryAttempt}`}>
          <div className="recovery-spinner"></div>
        </div>
      )}
    </div>
  );
};

export default ConnectionStatus;