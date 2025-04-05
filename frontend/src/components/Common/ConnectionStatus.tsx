// src/components/Common/ConnectionStatus.tsx
import React from 'react';
// Import the necessary enums/types for props
import {
  ConnectionStatus as ConnectionStatusEnum, // Rename imported enum to avoid conflict
  ConnectionQuality
} from '../../services/connection/unified-connection-state'; // Adjust import path if needed

// Import the corresponding CSS file for styling
import './ConnectionStatus.css';

/**
 * Interface defining the props accepted by the ConnectionStatus component.
 * These props provide information about the connection's current state.
 */
interface ConnectionStatusProps {
  status: ConnectionStatusEnum; // The overall connection status (e.g., connected, disconnected)
  quality: ConnectionQuality; // The calculated connection quality (e.g., good, degraded)
  isRecovering: boolean; // Flag indicating if a recovery attempt is in progress
  recoveryAttempt: number; // The current recovery attempt number (if recovering)
  onManualReconnect: () => Promise<boolean>; // Callback function to trigger a manual reconnect attempt
  simulatorStatus: string; // The current status reported by the simulator
}

/**
 * ConnectionStatus Component:
 * Displays the current connection status, quality, simulator status,
 * and provides a button for manual reconnection attempts.
 */
const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  status,
  quality,
  isRecovering,
  recoveryAttempt,
  onManualReconnect,
  simulatorStatus
}) => {

  // Determine the text and CSS class based on the connection status
  const getStatusDisplay = () => {
    switch (status) {
      case ConnectionStatusEnum.CONNECTED:
        return { text: `Connected (${quality})`, className: quality.toLowerCase() };
      case ConnectionStatusEnum.CONNECTING:
        return { text: 'Connecting...', className: 'connecting' };
      case ConnectionStatusEnum.RECOVERING:
        return { text: `Reconnecting (Attempt ${recoveryAttempt})...`, className: 'recovering' };
      case ConnectionStatusEnum.DISCONNECTED:
        return { text: 'Disconnected', className: 'disconnected' };
      default:
        return { text: 'Unknown', className: 'unknown' };
    }
  };

  // Determine the CSS class for the simulator status text
  const getSimulatorStatusClass = (simStatus: string): string => {
    // Basic example, adjust based on your actual simulator statuses
    switch (simStatus?.toUpperCase()) {
      case 'RUNNING': return 'running';
      case 'STARTING': return 'starting';
      case 'STOPPING': return 'stopping';
      case 'STOPPED': return 'stopped';
      case 'ERROR': return 'error';
      default: return 'unknown';
    }
  };

  const { text: statusText, className: statusClass } = getStatusDisplay();
  const simulatorClass = getSimulatorStatusClass(simulatorStatus);

  // Handle button click for manual reconnect
  const handleReconnectClick = () => {
    console.log("Manual reconnect button clicked.");
    onManualReconnect().catch(err => {
      console.error("Manual reconnect failed:", err);
      // Optionally show a toast notification on failure
    });
  };

  return (
    <div className={`connection-indicator ${statusClass}`}>
      {/* Optional: Icon based on status */}
      {/* <span className="indicator-icon">🌐</span> */}
      <div className="indicator-text">
        <span className="status-text">{statusText}</span>
        <span className={`simulator-status ${simulatorClass}`}>
          Simulator: {simulatorStatus || 'N/A'}
        </span>
      </div>

      {/* Show reconnect button only when disconnected and not currently recovering/connecting */}
      {status === ConnectionStatusEnum.DISCONNECTED && !isRecovering && (
        <button
          className="reconnect-button"
          onClick={handleReconnectClick}
          disabled={isRecovering} // Disable if recovery is somehow active despite disconnected status
        >
          Reconnect
        </button>
      )}

      {/* Show spinner and attempt count when recovering */}
      {isRecovering && (
         <div className="recovery-progress" title={`Attempt ${recoveryAttempt}`}>
            <div className="recovery-spinner"></div>
         </div>
      )}
    </div>
  );
};

export default ConnectionStatus;
