// src/components/Common/ConnectionStatusBar.tsx
import React from 'react';
import { ConnectionStatus, ConnectionQuality } from '../../state/connection-state';
import './ConnectionStatusBar.css';

interface ConnectionStatusBarProps {
  state: {
    overallStatus: ConnectionStatus;
    webSocketStatus: ConnectionStatus;
    quality: ConnectionQuality;
    isRecovering: boolean;
    recoveryAttempt: number;
    heartbeatLatency?: number | null;
    simulatorStatus: string;
    lastConnectionError: string | null;
  };
  onManualReconnect?: () => void;
}

const ConnectionStatusBar: React.FC<ConnectionStatusBarProps> = ({ state, onManualReconnect }) => {
  // Destructure directly from the passed state object
  const {
    overallStatus,
    quality,
    simulatorStatus,
    isRecovering,
    recoveryAttempt,
    heartbeatLatency,
    lastConnectionError
  } = state;

  const getStatusText = () => {
    switch (overallStatus) {
      case ConnectionStatus.CONNECTED:
        // Don't show the quality if it's unknown
        return quality !== ConnectionQuality.UNKNOWN ? 
          `Connected (${quality})` : 
          'Connected';
      case ConnectionStatus.CONNECTING:
        return 'Connecting...';
      case ConnectionStatus.RECOVERING:
        const attemptText = recoveryAttempt && recoveryAttempt > 0 ? ` (Attempt ${recoveryAttempt})` : '';
        return `Reconnecting${attemptText}...`;
      case ConnectionStatus.DISCONNECTED:
         return `Disconnected${lastConnectionError ? `: ${lastConnectionError.substring(0, 50)}` : ''}${lastConnectionError && lastConnectionError.length > 50 ? '...' : ''}`;
      default:
        return 'Unknown';
    }
  };

  const getQualityClass = () => {
    if (overallStatus !== ConnectionStatus.CONNECTED) return 'unknown';
    switch(quality) {
        case ConnectionQuality.GOOD: return 'good';
        case ConnectionQuality.DEGRADED: return 'degraded';
        case ConnectionQuality.POOR: return 'poor';
        case ConnectionQuality.UNKNOWN:
        default: return 'good'; // Default to 'good' when connected but quality unknown
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

  return (
    <div className={`connection-status-bar ${getStatusClass()}`}>
      <div className="status-content">
        <span className="status-text">{getStatusText()}</span>
        {simulatorStatus && (
          <span className={`simulator-status ${getSimulatorStatusClass()}`}>
            Simulator: {simulatorStatus}
            {overallStatus === ConnectionStatus.CONNECTED && typeof heartbeatLatency === 'number' && heartbeatLatency >= 0 && 
            ` (${heartbeatLatency.toFixed(0)}ms)`}
          </span>
        )}
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
    </div>
  );
};

export default ConnectionStatusBar;