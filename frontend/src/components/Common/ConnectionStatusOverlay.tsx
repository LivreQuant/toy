// src/components/Common/ConnectionStatusOverlay.tsx
import React from 'react';
import { useConnection } from '../../contexts/ConnectionContext';
import { useAuth } from '../../contexts/AuthContext';
import { ConnectionStatus, ConnectionQuality } from '../../services/connection/unified-connection-state';
import './ConnectionStatusOverlay.css';

const ConnectionStatusOverlay: React.FC = () => {
  // Get authentication state
  const { isAuthenticated, isLoading } = useAuth();
  
  // Get connection state
  const {
    isConnected,
    isConnecting,
    isRecovering,
    connectionQuality,
    overallStatus,
    manualReconnect
  } = useConnection();

  // Only show overlay if:
  // 1. User is authenticated and auth check completed
  // 2. AND either disconnected or connected with poor quality
  const showOverlay = !isLoading && 
                       isAuthenticated && (
                        overallStatus === ConnectionStatus.DISCONNECTED ||
                        (isConnected && connectionQuality === ConnectionQuality.POOR)
                      );

  // If conditions aren't met, don't render the overlay
  if (!showOverlay) {
    return null;
  }

  // Helper function to get quality CSS class
  const getQualityClass = () => {
      switch (connectionQuality) {
          case ConnectionQuality.GOOD: return 'connection-quality-good';
          case ConnectionQuality.DEGRADED: return 'connection-quality-degraded';
          case ConnectionQuality.POOR: return 'connection-quality-poor';
          default: return '';
      }
  }

  // Event Handler
  const handleReconnect = () => {
    manualReconnect();
  };

  return (
    <div className="connection-status-overlay">
      <div className="connection-status-content">
        <h3>Connection Status</h3>
        <p>Current Status: {overallStatus}</p>
        {isConnected && (
            <p>Connection Quality: <span className={getQualityClass()}>{connectionQuality}</span></p>
        )}
        {overallStatus === ConnectionStatus.DISCONNECTED && (
            <p>The connection to the server has been lost.</p>
        )}
        {isConnected && connectionQuality === ConnectionQuality.POOR && (
            <p>Your connection quality is poor, which may affect performance.</p>
        )}

        {/* Show reconnect button if disconnected and not already trying */}
        {overallStatus === ConnectionStatus.DISCONNECTED && !isConnecting && !isRecovering && (
            <button onClick={handleReconnect} disabled={isConnecting || isRecovering}>
                Attempt Reconnect
            </button>
        )}
        {/* Optionally show reconnect button even if quality is just poor */}
        {isConnected && connectionQuality === ConnectionQuality.POOR && (
            <button onClick={handleReconnect} disabled={isConnecting || isRecovering}>
                Try Reconnecting
            </button>
        )}
      </div>
    </div>
  );
};

export default ConnectionStatusOverlay;