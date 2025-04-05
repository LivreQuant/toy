// src/components/Common/ConnectionStatus.tsx
import React from 'react';
// Import the hook to use the connection context
import { useConnection } from '../../contexts/ConnectionContext'; // Adjust path if needed
// Import enums for status and quality checking
import { ConnectionStatus as StatusEnum, ConnectionQuality } from '../../services/connection/unified-connection-state'; // Adjust path if needed
import './ConnectionStatus.css';

// This component displays the current connection status, quality, and provides a reconnect button.
// It now gets all its data directly from the useConnection hook.
const ConnectionStatusDisplay: React.FC = () => {
  // --- Refactored: Get state and actions from the updated context ---
  const {
    isConnecting,    // Needed to disable button
    isRecovering,    // Needed for recovery indicator and disabling button
    recoveryAttempt, // Display current attempt number during recovery
    manualReconnect, // Function to trigger manual reconnect
    overallStatus,   // The primary status (CONNECTED, DISCONNECTED, etc.)
    connectionQuality, // Quality level (GOOD, DEGRADED, POOR)
    simulatorStatus  // Status of the simulator (RUNNING, STOPPED, etc.)
  } = useConnection();

  // --- Helper function to determine CSS class based on status and quality ---
  const getStatusClassName = () => {
      switch (overallStatus) {
          case StatusEnum.CONNECTED:
              // If connected, class depends on quality
              return connectionQuality === ConnectionQuality.GOOD ? 'good' :
                     connectionQuality === ConnectionQuality.DEGRADED ? 'degraded' : 'poor';
          case StatusEnum.CONNECTING: return 'connecting';
          case StatusEnum.RECOVERING: return 'recovering';
          case StatusEnum.DISCONNECTED: return 'disconnected';
          default: return 'unknown'; // Fallback for any unexpected status
      }
  };

  // --- Helper function to format status text ---
  const getStatusText = () => {
      switch (overallStatus) {
          case StatusEnum.CONNECTED: return 'Connected';
          case StatusEnum.CONNECTING: return 'Connecting...';
          case StatusEnum.RECOVERING: return `Reconnecting (Attempt ${recoveryAttempt})...`;
          case StatusEnum.DISCONNECTED: return 'Disconnected';
          default: return 'Unknown';
      }
  }

  return (
    // Apply the dynamic CSS class to the main container
    <div className={`connection-indicator ${getStatusClassName()}`}>
      {/* TODO: Add an icon based on status/quality if desired */}
      {/* <span className="indicator-icon">ICON</span> */}

      <div className="indicator-text">
        {/* Display the formatted status text */}
        <span className="status-text">{getStatusText()}</span>
        {/* Show connection quality only when connected */}
        {overallStatus === StatusEnum.CONNECTED && <span>Quality: {connectionQuality}</span>}
        {/* Display the simulator status */}
        <span className={`simulator-status ${simulatorStatus?.toLowerCase()}`}>
            Simulator: {simulatorStatus || 'N/A'}
        </span>
      </div>

      {/* Show recovery progress indicator if recovering */}
      {isRecovering && (
          <div className="recovery-progress">
              {/* Optionally show attempt number here too */}
              {/* <span>Attempt {recoveryAttempt}...</span> */}
              <div className="recovery-spinner" title={`Reconnecting attempt ${recoveryAttempt}`}></div>
          </div>
      )}

      {/* Show manual reconnect button only if disconnected AND not currently connecting/recovering */}
      {overallStatus === StatusEnum.DISCONNECTED && !isConnecting && !isRecovering && (
        <button
          className="reconnect-button"
          onClick={manualReconnect}
          // Ensure button isn't clickable while actions are in progress (redundant check but safe)
          disabled={isConnecting || isRecovering}
        >
          Reconnect
        </button>
      )}
    </div>
  );
};

export default ConnectionStatusDisplay;
