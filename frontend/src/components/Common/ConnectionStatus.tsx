import React from 'react';
import './ConnectionStatus.css';

interface ConnectionStatusProps {
  isConnected: boolean;
  isConnecting: boolean;
  connectionQuality: string;
  simulatorStatus: string;
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  isConnected,
  isConnecting,
  connectionQuality,
  simulatorStatus
}) => {
  // Determine connection status
  let statusIcon = '❓';
  let statusClass = 'unknown';
  let statusText = 'Unknown';
  
  if (!isConnected && isConnecting) {
    statusIcon = '🔄';
    statusClass = 'connecting';
    statusText = 'Connecting...';
  } else if (!isConnected) {
    statusIcon = '❌';
    statusClass = 'disconnected';
    statusText = 'Disconnected';
  } else if (connectionQuality === 'good') {
    statusIcon = '✅';
    statusClass = 'good';
    statusText = 'Connected';
  } else if (connectionQuality === 'degraded') {
    statusIcon = '⚠️';
    statusClass = 'degraded';
    statusText = 'Connection Degraded';
  } else if (connectionQuality === 'poor') {
    statusIcon = '🔴';
    statusClass = 'poor';
    statusText = 'Connection Poor';
  }
  
  // Determine simulator status
  let simulatorStatusText = '';
  let simulatorStatusClass = '';
  
  switch (simulatorStatus) {
    case 'RUNNING':
      simulatorStatusText = 'Simulator Running';
      simulatorStatusClass = 'running';
      break;
    case 'STARTING':
      simulatorStatusText = 'Simulator Starting...';
      simulatorStatusClass = 'starting';
      break;
    case 'STOPPING':
      simulatorStatusText = 'Simulator Stopping...';
      simulatorStatusClass = 'stopping';
      break;
    case 'STOPPED':
      simulatorStatusText = 'Simulator Stopped';
      simulatorStatusClass = 'stopped';
      break;
    case 'ERROR':
      simulatorStatusText = 'Simulator Error';
      simulatorStatusClass = 'error';
      break;
    default:
      simulatorStatusText = 'Simulator Status Unknown';
      simulatorStatusClass = 'unknown';
  }
  
  return (
    <div className={`connection-indicator ${statusClass}`}>
      <div className="indicator-icon">{statusIcon}</div>
      <div className="indicator-text">
        <div className="status-text">{statusText}</div>
        {simulatorStatus && (
          <div className={`simulator-status ${simulatorStatusClass}`}>
            {simulatorStatusText}
          </div>
        )}
      </div>
    </div>
  );
};

export default ConnectionStatus;