// src/components/Common/ConnectionStatusOverlay.tsx
import React from 'react';
// Import the hook to use the connection context
import { useConnection } from '../../contexts/ConnectionContext'; // Adjust path if needed
// Import enums for status and quality checking
import { ConnectionStatus, ConnectionQuality } from '../../services/connection/unified-connection-state'; // Adjust path if needed
import './ConnectionStatusOverlay.css';

// This component displays an overlay, potentially when the connection is poor or disconnected,
// offering a way to manually reconnect.
const ConnectionStatusOverlay: React.FC = () => {
  // --- Refactored: Get state and actions from the updated context ---
  const {
    isConnected,
    isConnecting,
    isRecovering,
    connectionQuality,
    overallStatus,
    manualReconnect // Get the reconnect action
  } = useConnection();

  // --- Determine if the overlay should be shown ---
  // Example Logic: Show if disconnected, or connected but with poor quality.
  // Adjust this logic based on when you want the overlay to appear.
  const showOverlay =
    overallStatus === ConnectionStatus.DISCONNECTED ||
    (isConnected && connectionQuality === ConnectionQuality.POOR);

  // If conditions aren't met, don't render the overlay
  if (!showOverlay) {
    return null;
  }

  // --- Helper function to get quality CSS class ---
  const getQualityClass = () => {
      switch (connectionQuality) {
          case ConnectionQuality.GOOD: return 'connection-quality-good';
          case ConnectionQuality.DEGRADED: return 'connection-quality-degraded';
          case ConnectionQuality.POOR: return 'connection-quality-poor';
          default: return '';
      }
  }

  // --- Event Handler ---
  const handleReconnect = () => {
    manualReconnect(); // Call the action from the context
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

