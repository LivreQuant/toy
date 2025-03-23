// src/components/Connection/ConnectionStatus.tsx
import React from 'react';
import { useConnection } from '../../contexts/ConnectionContext';
import './ConnectionStatus.css';

export const ConnectionStatus: React.FC = () => {
  const { 
    isConnected, 
    isConnecting, 
    connectionQuality, 
    lastHeartbeatTime, 
    heartbeatLatency,
    podName,
    podSwitched,
    canSubmitOrders
  } = useConnection();
  
  // Calculate time since last heartbeat
  const timeSinceHeartbeat = lastHeartbeatTime > 0 
    ? Math.floor((Date.now() - lastHeartbeatTime) / 1000) 
    : null;
  
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
  
  // Add order submission status
  const orderStatusText = canSubmitOrders
    ? 'Order submission enabled'
    : 'Order submission disabled';
  
  return (
    <div className={`connection-indicator ${statusClass}`}>
      <div className="indicator-icon">{statusIcon}</div>
      <div className="indicator-text">
        <div className="status-text">{statusText}</div>
        <div className="order-status">{orderStatusText}</div>
        {heartbeatLatency !== null && (
          <div className="latency">
            Latency: {heartbeatLatency}ms
          </div>
        )}
        {timeSinceHeartbeat !== null && (
          <div className="last-heartbeat">
            Last heartbeat: {timeSinceHeartbeat}s ago
          </div>
        )}
        {podName && (
          <div className="pod-info">
            Pod: {podName.substring(0, 8)}...
            {podSwitched && <span className="pod-switched">(changed)</span>}
          </div>
        )}
      </div>
    </div>
  );
};

export default ConnectionStatus;