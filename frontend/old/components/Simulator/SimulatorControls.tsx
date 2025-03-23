// src/components/Simulator/SimulatorControls.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useConnection } from '../../contexts/ConnectionContext';
import Loading from '../Common/Loading';
import './SimulatorControls.css';

interface SimulatorControlsProps {
  onStartSimulator?: () => void;
  onStopSimulator?: () => void;
}

const SimulatorControls: React.FC<SimulatorControlsProps> = ({
  onStartSimulator,
  onStopSimulator
}) => {
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { 
    isConnected, 
    sessionId, 
    simulatorId, 
    simulatorStatus 
  } = useConnection();
  
  const navigate = useNavigate();
  
  // Reset state when connection is lost
  useEffect(() => {
    if (!isConnected) {
      setIsStarting(false);
      setIsStopping(false);
    }
  }, [isConnected]);
  
  const handleStartSimulator = async () => {
    if (!isConnected || !sessionId) {
      setError('Not connected to server');
      return;
    }
    
    setIsStarting(true);
    setError(null);
    
    try {
      // Call your API to start the simulator
      const token = localStorage.getItem('token');
      
      if (!token) {
        throw new Error('Authentication token not found');
      }
      
      const response = await fetch('/api/simulator/start', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ sessionId })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.message || 'Failed to start simulator');
      }
      
      // Call callback if provided
      if (onStartSimulator) {
        onStartSimulator();
      }
      
      // Navigate to simulator page
      navigate('/simulator');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start simulator');
    } finally {
      setIsStarting(false);
    }
  };
  
  const handleStopSimulator = async () => {
    if (!isConnected || !sessionId || !simulatorId) {
      setError('No active simulator to stop');
      return;
    }
    
    setIsStopping(true);
    setError(null);
    
    try {
      // Call your API to stop the simulator
      const token = localStorage.getItem('token');
      
      if (!token) {
        throw new Error('Authentication token not found');
      }
      
      const response = await fetch('/api/simulator/stop', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ simulatorId })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.message || 'Failed to stop simulator');
      }
      
      // Call callback if provided
      if (onStopSimulator) {
        onStopSimulator();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop simulator');
    } finally {
      setIsStopping(false);
    }
  };
  
  const handleOpenSimulator = () => {
    navigate('/simulator');
  };
  
  const getStatusClass = () => {
    switch (simulatorStatus) {
      case 'RUNNING': return 'status-running';
      case 'STARTING': return 'status-starting';
      case 'STOPPING': return 'status-stopping';
      case 'ERROR': return 'status-error';
      default: return 'status-stopped';
    }
  };
  
  return (
    <div className="simulator-controls">
      <h2>Exchange Simulator</h2>
      
      {error && <div className="simulator-error">{error}</div>}
      
      <div className={`simulator-status ${getStatusClass()}`}>
        <div className="status-indicator"></div>
        <div className="status-text">
          {simulatorStatus || 'STOPPED'}
        </div>
      </div>
      
      <div className="simulator-actions">
        {(!simulatorId || simulatorStatus === 'STOPPED') && (
          <button
            className="start-button"
            onClick={handleStartSimulator}
            disabled={isStarting || !isConnected}
          >
            {isStarting ? <Loading size="small" /> : 'Start Simulator'}
          </button>
        )}
        
        {simulatorId && simulatorStatus === 'RUNNING' && (
          <>
            <button
              className="open-button"
              onClick={handleOpenSimulator}
            >
              Open Simulator
            </button>
            
            <button
              className="stop-button"
              onClick={handleStopSimulator}
              disabled={isStopping || !isConnected}
            >
              {isStopping ? <Loading size="small" /> : 'Stop Simulator'}
            </button>
          </>
        )}
        
        {simulatorId && (simulatorStatus === 'STARTING' || simulatorStatus === 'STOPPING') && (
          <div className="simulator-transitioning">
            <Loading size="small" />
            <span>{simulatorStatus === 'STARTING' ? 'Starting simulator...' : 'Stopping simulator...'}</span>
          </div>
        )}
      </div>
      
      <div className="simulator-info">
        {simulatorId && (
          <div className="simulator-id">
            Simulator ID: {simulatorId.substring(0, 8)}...
          </div>
        )}
        
        {simulatorStatus === 'RUNNING' && (
          <div className="session-info">
            Session active and connected
          </div>
        )}
      </div>
    </div>
  );
};

export default SimulatorControls;