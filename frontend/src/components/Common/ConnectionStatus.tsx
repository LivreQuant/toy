// src/components/Common/ConnectionStatus.tsx

import React from 'react';
import './ConnectionStatus.css';
import { useConnection } from '../../contexts/ConnectionContext';

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
  const { 
    isRecovering,
    recoveryAttempt,
    manualReconnect
  } = useConnection();
  
  // Determine connection status
  let statusIcon = '❓';
  let statusClass = 'unknown';
  let statusText = 'Unknown Connection Status';
  
  if (isRecovering) {
    statusIcon = '🔄';
    statusClass = 'recovering';
    statusText = `Reconnecting (Attempt ${recoveryAttempt})...`;
  } else if (!isConnected && isConnecting) {
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
  
  // Handle reconnect button click
  const handleReconnect = async () => {
    try {
      await manualReconnect();
    } catch (error) {
      console.error('Manual reconnection failed:', error);
    }
  };
  
  return (
    <div className={`connection-indicator ${statusClass}`}>
      <div className="indicator-icon">{statusIcon}</div>
      <div className="indicator-text">
        <div className="status-text">{statusText}</div>
        {simulatorStatus && (
          <div className={`simulator-status ${simulatorStatus.toLowerCase()}`}>
            {getSimulatorStatusText(simulatorStatus)}
          </div>
        )}
      </div>
      
      {/* Add reconnect button when disconnected */}
      {!isConnected && !isConnecting && !isRecovering && (
        <button 
          className="reconnect-button" 
          onClick={handleReconnect}
        >
          Reconnect
        </button>
      )}
      
      {/* Show progress when recovering */}
      {isRecovering && (
        <div className="recovery-progress">
          <div className="recovery-spinner"></div>
        </div>
      )}
    </div>
  );
};

// Helper function to get readable simulator status text
function getSimulatorStatusText(status: string): string {
  switch (status) {
    case 'RUNNING': return 'Simulator Running';
    case 'STARTING': return 'Simulator Starting...';
    case 'STOPPING': return 'Simulator Stopping...';
    case 'STOPPED': return 'Simulator Stopped';
    case 'ERROR': return 'Simulator Error';
    default: return 'Simulator Status Unknown';
  }
}

export default ConnectionStatus;