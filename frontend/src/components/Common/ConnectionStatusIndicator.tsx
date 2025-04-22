// src/components/Common/ConnectionStatusIndicator.tsx
import React from 'react';
// Import Enums from AppStateService (or a dedicated types file)
import { ConnectionStatus, ConnectionQuality } from '../../state/connection-state';
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
    quality, // FIX: Use 'quality' instead of 'connectionQuality'
    simulatorStatus,
    isRecovering,
    recoveryAttempt,
    heartbeatLatency,
    lastConnectionError, // Get last error message
  } = state;

  const getStatusText = () => {
    switch (overallStatus) {
      case ConnectionStatus.CONNECTED:
        return `Connected (${quality})`; // Use quality directly
      case ConnectionStatus.CONNECTING:
        return 'Connecting...';
      case ConnectionStatus.RECOVERING:
        const attemptText = recoveryAttempt && recoveryAttempt > 0 ? ` (Attempt ${recoveryAttempt})` : '';
        return `Reconnecting${attemptText}...`;
      case ConnectionStatus.DISCONNECTED:
         // Show error message if available and disconnected
         return `Disconnected${lastConnectionError ? `: ${lastConnectionError.substring(0, 50)}` : ''}${lastConnectionError && lastConnectionError.length > 50 ? '...' : ''}`; // Truncate long errors
      default:
        return 'Unknown';
    }
  };

  const getQualityClass = () => {
      if (overallStatus !== ConnectionStatus.CONNECTED) return 'unknown';
      switch(quality) { // FIX: Use 'quality'
          case ConnectionQuality.GOOD: return 'good';
          case ConnectionQuality.DEGRADED: return 'degraded';
          case ConnectionQuality.POOR: return 'poor';
          case ConnectionQuality.UNKNOWN:
          default: return 'unknown';
      }
  }

  const getStatusClass = () => {
     switch (overallStatus) {
        case ConnectionStatus.CONNECTED: return getQualityClass();
        case ConnectionStatus.CONNECTING: return 'connecting';
        case ConnectionStatus.RECOVERING: return 'recovering';
        case ConnectionStatus.DISCONNECTED: return 'disconnected';
        default: return 'unknown';
     }
  }

  const getSimulatorStatusClass = () => {
     return simulatorStatus?.toLowerCase() ?? 'unknown';
  }

  const showReconnectButton = overallStatus === ConnectionStatus.DISCONNECTED && !isRecovering && !!onManualReconnect;

  // Determine title/tooltip text for the indicator
  const getTooltipText = () => {
     let text = `Status: ${overallStatus}`;
     if (overallStatus === ConnectionStatus.CONNECTED) {
         text += ` | Quality: ${quality}`;
         if (typeof heartbeatLatency === 'number' && heartbeatLatency >= 0) {
             text += ` | Latency: ${heartbeatLatency.toFixed(0)}ms`;
         }
     }
     if (overallStatus === ConnectionStatus.RECOVERING && recoveryAttempt > 0) {
         text += ` | Attempt: ${recoveryAttempt}`;
     }
     text += ` | Simulator: ${simulatorStatus}`;
     if (overallStatus === ConnectionStatus.DISCONNECTED && lastConnectionError) {
         text += ` | Error: ${lastConnectionError}`;
     }
     return text;
  }

  return (
    <div className={`connection-indicator ${getStatusClass()}`} title={getTooltipText()}>
       {/* Icons can be improved with an icon library */}
       <span className="indicator-icon">
          {overallStatus === ConnectionStatus.CONNECTED && '🟢'}
          {overallStatus === ConnectionStatus.CONNECTING && '🟡'}
          {/* Show spinner inline when recovering */}
          {overallStatus === ConnectionStatus.RECOVERING && <div className="recovery-spinner" title={`Reconnecting Attempt ${recoveryAttempt}`}></div>}
          {overallStatus === ConnectionStatus.DISCONNECTED && '🔴'}
          {/* Fallback icon */}
          {overallStatus !== ConnectionStatus.CONNECTED &&
           overallStatus !== ConnectionStatus.CONNECTING &&
           overallStatus !== ConnectionStatus.RECOVERING &&
           overallStatus !== ConnectionStatus.DISCONNECTED && '⚪'}
       </span>
      <div className="indicator-text">
        <span className="status-text">{getStatusText()}</span>
        <span className={`simulator-status ${getSimulatorStatusClass()}`}>
            Simulator: {simulatorStatus}
            {overallStatus === ConnectionStatus.CONNECTED && typeof heartbeatLatency === 'number' && heartbeatLatency >= 0 && ` (${heartbeatLatency.toFixed(0)}ms)`}
        </span>
      </div>
       {showReconnectButton && (
           <button
               onClick={onManualReconnect}
               className="reconnect-button"
               title="Attempt to reconnect"
           >
               Reconnect
           </button>
       )}
       {/* Optional: Show spinner without button when recovering */}
       {/* {isRecovering && !showReconnectButton && (
           <div className="recovery-progress">
               <div className="recovery-spinner"></div>
           </div>
       )} */}
    </div>
  );
};

export default ConnectionStatusIndicator;