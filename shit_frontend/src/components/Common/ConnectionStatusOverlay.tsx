// src/components/Common/ConnectionStatusOverlay.tsx
import React from 'react';
import { useConnectionState, useConnectionActions } from '../../contexts/ConnectionContext';
import { useAuthState } from '../../hooks/useAppState';
import { ConnectionStatus, ConnectionQuality } from '../../services/connection/unified-connection-state';
import './ConnectionStatusOverlay.css';

const ConnectionStatusOverlay: React.FC = () => {
  // Get authentication state using reactive state hook
  const authState = useAuthState();
  
  // Get connection state using reactive state hook
  const connectionState = useConnectionState();
  
  // Get connection actions from context
  const { manualReconnect } = useConnectionActions();

  // Only show overlay if:
  // 1. User is authenticated and auth check completed
  // 2. AND either disconnected or connected with poor quality
  const showOverlay = !authState.isLoading && 
                       authState.isAuthenticated && (
                        connectionState.status === ConnectionStatus.DISCONNECTED ||
                        (connectionState.status === ConnectionStatus.CONNECTED && connectionState.quality === ConnectionQuality.POOR)
                      );

  // If conditions aren't met, don't render the overlay
  if (!showOverlay) {
    return null;
  }

  // Helper function to get quality CSS class
  const getQualityClass = () => {
      switch (connectionState.quality) {
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
        <p>Current Status: {connectionState.status}</p>
        {connectionState.status === ConnectionStatus.CONNECTED && (
            <p>Connection Quality: <span className={getQualityClass()}>{connectionState.quality}</span></p>
        )}
        {connectionState.status === ConnectionStatus.DISCONNECTED && (
            <p>The connection to the server has been lost.</p>
        )}
        {connectionState.status === ConnectionStatus.CONNECTED && connectionState.quality === ConnectionQuality.POOR && (
            <p>Your connection quality is poor, which may affect performance.</p>
        )}

        {/* Show reconnect button if disconnected and not already trying */}
        {connectionState.status === ConnectionStatus.DISCONNECTED && 
         !connectionState.isConnecting && 
         !connectionState.isRecovering && (
            <button onClick={handleReconnect} disabled={connectionState.isConnecting || connectionState.isRecovering}>
                Attempt Reconnect
            </button>
        )}
        {/* Optionally show reconnect button even if quality is just poor */}
        {connectionState.status === ConnectionStatus.CONNECTED && 
         connectionState.quality === ConnectionQuality.POOR && (
            <button onClick={handleReconnect} disabled={connectionState.isConnecting || connectionState.isRecovering}>
                Try Reconnecting
            </button>
        )}
      </div>
    </div>
  );
};

export default ConnectionStatusOverlay;