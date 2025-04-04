// src/components/Common/ConnectionStatusOverlay.tsx
import React, { useEffect } from 'react';
import { useConnection } from '../../contexts/ConnectionContext';
import './ConnectionStatusOverlay.css';
import { toastService } from '../../services/notification/toast-service';

const ConnectionStatusOverlay: React.FC = () => {
  const { 
    isConnected, 
    connectionQuality, 
    connectionState,
    isRecovering,
    manualReconnect
  } = useConnection();

  // React to connection changes and show toasts
  useEffect(() => {
    // Only show initial disconnection toast
    if (!isConnected && !isRecovering) {
      toastService.error(`Connection Lost. Status: ${connectionState.simulatorStatus}`, 7000);
    } else if (connectionQuality === 'degraded') {
      toastService.warning('Connection quality is degraded', 5000);
    }
  }, [isConnected, connectionQuality, connectionState.simulatorStatus, isRecovering]);

  // If connected, don't show the overlay
  if (isConnected) return null;
  
  // If recovery is in progress, show a less disruptive indicator
  if (isRecovering) {
    return (
      <div className="connection-status-overlay recovering">
        <div className="connection-status-content">
          <h3>Reconnecting...</h3>
          <div className="recovery-progress-indicator">
            <div className="recovery-spinner"></div>
            <p>Attempt {connectionState.recoveryAttempt}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="connection-status-overlay">
      <div className="connection-status-content">
        <h3>Connection Issue</h3>
        <p>Status: {connectionState.simulatorStatus}</p>
        <p className={`connection-quality-${connectionQuality}`}>
          Quality: {connectionQuality}
        </p>
        
        {/* Show service-specific statuses */}
        <div className="service-statuses">
          <p className={connectionState.webSocketState?.status === 'connected' ? 'status-good' : 'status-bad'}>
            WebSocket: {connectionState.webSocketState?.status || 'unknown'}
          </p>
          <p className={connectionState.sseState?.status === 'connected' ? 'status-good' : 'status-bad'}>
            Data Stream: {connectionState.sseState?.status || 'unknown'}
          </p>
        </div>

        <button onClick={() => {
          manualReconnect();
          toastService.info('Attempting to reconnect...', 3000);
        }}>
          Reconnect
        </button>
      </div>
    </div>
  );
};

export default ConnectionStatusOverlay;