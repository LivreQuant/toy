// src/components/Common/ConnectionStatusIndicator.tsx (Corrected Import)
import React from 'react';
// Import Enums from AppStateService (or a dedicated types file)
import { ConnectionStatus, ConnectionQuality, AppState } from '../../services/state/app-state.service';
import './ConnectionStatus.css'; // Import styles

interface ConnectionStatusIndicatorProps {
  // Expect the 'connection' slice of the AppState
  state: AppState['connection'];
  onManualReconnect?: () => void; // Callback to trigger manual reconnect
}

const ConnectionStatusIndicator: React.FC<ConnectionStatusIndicatorProps> = ({ state, onManualReconnect }) => {
  // Destructure directly from the passed state object
  const {
    overallStatus,
    connectionQuality,
    simulatorStatus,
    isRecovering,
    recoveryAttempt,
    heartbeatLatency,
  } = state;

  const getStatusText = () => {
    switch (overallStatus) {
      case ConnectionStatus.CONNECTED:
        // Show quality only when connected
        return `Connected (${connectionQuality})`;
      case ConnectionStatus.CONNECTING:
        return 'Connecting...';
      case ConnectionStatus.RECOVERING:
        // Display attempt number if available and > 0
        const attemptText = recoveryAttempt && recoveryAttempt > 0 ? ` (Attempt ${recoveryAttempt})` : '';
        return `Reconnecting${attemptText}...`;
      case ConnectionStatus.DISCONNECTED:
        return 'Disconnected';
      default:
        // Ensure TS knows this case is handled (or throw error)
        const exhaustiveCheck: never = overallStatus;
        return 'Unknown';
    }
  };

  const getQualityClass = () => {
      // Determine CSS class based on quality, only relevant when connected
      if (overallStatus !== ConnectionStatus.CONNECTED) return 'unknown'; // Default class if not connected
      switch(connectionQuality) {
          case ConnectionQuality.GOOD: return 'good';
          case ConnectionQuality.DEGRADED: return 'degraded';
          case ConnectionQuality.POOR: return 'poor';
          case ConnectionQuality.UNKNOWN:
          default: return 'unknown';
      }
  }

  // Determine the main CSS class based on the overall status
  const getStatusClass = () => {
     switch (overallStatus) {
        case ConnectionStatus.CONNECTED: return getQualityClass(); // Use quality class when connected
        case ConnectionStatus.CONNECTING: return 'connecting';
        case ConnectionStatus.RECOVERING: return 'recovering';
        case ConnectionStatus.DISCONNECTED: return 'disconnected';
        default: return 'unknown'; // Default for any unexpected status
     }
  }

  // Get CSS class for simulator status text color
  const getSimulatorStatusClass = () => {
     // Use lowercase status name, ensure it matches CSS class names
     return simulatorStatus?.toLowerCase() ?? 'unknown';
  }

  // Determine if the manual reconnect button should be shown
  // Show if explicitly disconnected, not currently recovering, and handler provided
  const showReconnectButton = overallStatus === ConnectionStatus.DISCONNECTED && !isRecovering && !!onManualReconnect;

  return (
    <div className={`connection-indicator ${getStatusClass()}`}>
       {/* Use appropriate icons based on status */}
       <span className="indicator-icon">
          {overallStatus === ConnectionStatus.CONNECTED && '🟢'}
          {overallStatus === ConnectionStatus.CONNECTING && '🟡'}
          {/* Show spinner inline when recovering */}
          {overallStatus === ConnectionStatus.RECOVERING && <div className="recovery-spinner" title={`Reconnecting Attempt ${recoveryAttempt}`}></div>}
          {overallStatus === ConnectionStatus.DISCONNECTED && '🔴'}
          {/* Fallback icon for Unknown status */}
          {overallStatus !== ConnectionStatus.CONNECTED &&
           overallStatus !== ConnectionStatus.CONNECTING &&
           overallStatus !== ConnectionStatus.RECOVERING &&
           overallStatus !== ConnectionStatus.DISCONNECTED && '⚪'}
       </span>
      <div className="indicator-text">
        <span className="status-text">{getStatusText()}</span>
        <span className={`simulator-status ${getSimulatorStatusClass()}`}>
            {/* Conditionally show simulator status and latency */}
            Simulator: {simulatorStatus}
            {/* Show latency only when connected and latency is available */}
            {overallStatus === ConnectionStatus.CONNECTED && typeof heartbeatLatency === 'number' && heartbeatLatency >= 0 && ` (Latency: ${heartbeatLatency.toFixed(0)}ms)`}
        </span>
      </div>
      {/* Show reconnect button only when disconnected and not already recovering */}
       {showReconnectButton && (
           <button
               onClick={onManualReconnect}
               className="reconnect-button"
               title="Attempt to reconnect"
           >
               Reconnect
           </button>
       )}
    </div>
  );
};

export default ConnectionStatusIndicator;