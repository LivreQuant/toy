// src/components/ReconnectionStatus.tsx
import React from 'react';
import { useConnection } from '../contexts/ConnectionContext';

const ReconnectionStatus: React.FC = () => {
  const { 
    isConnected, 
    isConnecting, 
    reconnectAttempt, 
    maxReconnectAttempts,
    error,
    reconnect
  } = useConnection();
  
  if (isConnected) {
    return null; // Don't show anything when connected
  }
  
  return (
    <div className="reconnection-status">
      {isConnecting ? (
        <div className="reconnecting">
          <div className="spinner"></div>
          <div className="message">
            Reconnecting... Attempt {reconnectAttempt} of {maxReconnectAttempts}
          </div>
        </div>
      ) : error ? (
        <div className="connection-error">
          <div className="error-icon">⚠️</div>
          <div className="message">{error}</div>
          <button className="retry-button" onClick={reconnect}>
            Retry Connection
          </button>
        </div>
      ) : null}
    </div>
  );
};

export default ReconnectionStatus;