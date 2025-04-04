// src/components/Common/ConnectionStatusOverlay.tsx
import React, { useEffect } from 'react';
import { useConnection } from '../../contexts/ConnectionContext';
import { useToast } from '../../contexts/ToastContext';
import './ConnectionStatusOverlay.css';

const ConnectionStatusOverlay: React.FC = () => {
  const { 
    isConnected, 
    connectionQuality, 
    connectionState,
    isRecovering,
    reconnect,
    manualReconnect
  } = useConnection();
  const { addToast } = useToast();
  
  // React to connection changes and show toasts
  useEffect(() => {
    // Only show initial disconnection toast
    if (!isConnected && !isRecovering) {
      addToast({
        type: 'error',
        message: `Connection Lost. Status: ${connectionState.simulatorStatus}`,
        duration: 7000
      });
    } else if (connectionQuality === 'degraded') {
      addToast({
        type: 'warning',
        message: 'Connection quality is degraded',
        duration: 5000
      });
    }
  }, [isConnected, connectionQuality, connectionState.simulatorStatus, isRecovering, addToast]);

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
          addToast({
            type: 'info',
            message: 'Attempting to reconnect...',
            duration: 3000
          });
        }}>
          Reconnect
        </button>
      </div>
    </div>
  );
};

export default ConnectionStatusOverlay;