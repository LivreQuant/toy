// src/components/Common/ConnectionStatus.tsx
import React from 'react';
import { useAuth } from '../../contexts/AuthContext';
import {
  ConnectionStatus as ConnectionStatusEnum,
  ConnectionQuality
} from '../../services/connection/unified-connection-state';
import './ConnectionStatus.css';

interface ConnectionStatusProps {
  status: ConnectionStatusEnum;
  quality: ConnectionQuality;
  isRecovering: boolean;
  recoveryAttempt: number;
  onManualReconnect: () => Promise<boolean>;
  simulatorStatus: string;
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  status,
  quality,
  isRecovering,
  recoveryAttempt,
  onManualReconnect,
  simulatorStatus
}) => {
  // Authentication context
  const { isAuthenticated, isLoading } = useAuth();

  // If not authenticated or still loading, don't show anything
  if (!isAuthenticated || isLoading) {
    return null;
  }

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
    });
  };

  return (
    <div className={`connection-indicator ${statusClass}`}>
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
          disabled={isRecovering}
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