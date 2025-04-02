// src/components/Common/ConnectionStatusOverlay.tsx
import React from 'react';
import { useConnection } from '../../contexts/ConnectionContext';
import { useToast } from '../../contexts/ToastContext';
import './ConnectionStatusOverlay.css';

const ConnectionStatusOverlay: React.FC = () => {
  const { 
    isConnected, 
    connectionQuality, 
    connectionState,
    reconnect 
  } = useConnection();
  const { addToast } = useToast();
  
  // React to connection changes and show toasts
  React.useEffect(() => {
    if (!isConnected) {
      addToast({
        type: 'error',
        message: `Connection Lost. Status: ${connectionState.simulatorStatus}`,
        duration: 7000
      });
    } else if (connectionQuality === 'degraded') {
      addToast({
        type: 'warning',
        message: 'Connection quality is degraded',
        duration: 5000
      });
    }
  }, [isConnected, connectionQuality, connectionState.simulatorStatus, addToast]);

  // Reconnection handler with toast feedback
  const handleReconnect = () => {
    reconnect();
    addToast({
      type: 'info',
      message: 'Attempting to reconnect to trading servers...',
      duration: 5000
    });
  };
  
  // Render nothing if connected
  if (isConnected) return null;

  return (
    <div className="connection-status-overlay">
      <div className="connection-status-content">
        <h3>Connection Issue</h3>
        <p>Status: {connectionState.simulatorStatus}</p>
        <p className={`connection-quality-${connectionQuality}`}>
          Quality: {connectionQuality}
        </p>
        <button onClick={() => {
          reconnect();
          addToast({
            type: 'info',
            message: 'Attempting to reconnect...',
            duration: 3000
          });
        }}>
          Reconnect
        </button>
      </div>
    </div>
  );
};

export default ConnectionStatusOverlay;