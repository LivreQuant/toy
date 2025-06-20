// src/pages/SimulatorPage.tsx
import React, { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useConnection } from '../hooks/useConnection';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useToast } from '../hooks/useToast';
import Container from '../components/Dashboard/Container/core/Container';
import './SimulatorPage.css';

const SimulatorPage: React.FC = () => {
  useRequireAuth();
  const { simulationId } = useParams<{ simulationId: string }>();
  const { connectionManager, connectionState, isConnected } = useConnection();
  const { addToast } = useToast();
  const navigate = useNavigate();

  // Get simulator status from connection state
  const simulatorStatus = connectionState?.simulatorStatus || 'UNKNOWN';
  const isSimulatorRunning = simulatorStatus === 'RUNNING';
  const isSimulatorBusy = simulatorStatus === 'STARTING' || simulatorStatus === 'STOPPING';

  // Monitor simulator status and redirect if not running
  useEffect(() => {
    // Only check if we have a connection and the status is stable
    if (!isConnected) return;
    
    // If simulator stopped unexpectedly, redirect back to book details
    if (simulatorStatus === 'STOPPED' || simulatorStatus === 'ERROR') {
      console.log(`📡 Simulator status changed to ${simulatorStatus}, redirecting to book details`);
      addToast('warning', `Simulator ${simulatorStatus.toLowerCase()}. Returning to book details.`);
      navigate(`/${simulationId}`);
      return;
    }
    
    // If we've been here a while and simulator never started, redirect
    const timeoutId = setTimeout(() => {
      if (!isSimulatorRunning && !isSimulatorBusy) {
        console.log('📡 Simulator failed to start within timeout, redirecting');
        addToast('error', 'Simulator failed to start. Returning to book details.');
        navigate(`/${simulationId}`);
      }
    }, 10000); // 10 second timeout
    
    return () => clearTimeout(timeoutId);
  }, [isConnected, simulatorStatus, isSimulatorRunning, isSimulatorBusy, simulationId, navigate, addToast]);

  // Show loading while waiting for connection
  if (!isConnected) {
    return (
      <div style={{ 
        height: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        flexDirection: 'column',
        gap: '20px',
        backgroundColor: '#1f2836',
        color: 'white'
      }}>
        <div className="loading-spinner" style={{
          width: '40px',
          height: '40px',
          border: '4px solid #333',
          borderTop: '4px solid #00E5FF',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }}></div>
        <h2>Connecting to Trading Platform...</h2>
        <p>Establishing secure connection...</p>
      </div>
    );
  }

  // Show loading while simulator is starting
  if (isSimulatorBusy) {
    return (
      <div style={{ 
        height: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        flexDirection: 'column',
        gap: '20px',
        backgroundColor: '#1f2836',
        color: 'white'
      }}>
        <div className="loading-spinner" style={{
          width: '40px',
          height: '40px',
          border: '4px solid #333',
          borderTop: '4px solid #00E5FF',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }}></div>
        <h2>Initializing Trading Simulator...</h2>
        <p>Status: {simulatorStatus}</p>
        <p>Please wait while we prepare your trading environment...</p>
      </div>
    );
  }

  // Main case: Simulator is running, show the trading dashboard
  if (isSimulatorRunning) {
    return (
      <div style={{ height: '100vh', width: '100%' }}>
        <Container/>
      </div>
    );
  }

  // Fallback: Simulator is not running and not starting
  return (
    <div style={{ 
      height: '100vh', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      flexDirection: 'column',
      gap: '20px',
      backgroundColor: '#1f2836',
      color: 'white'
    }}>
      <h2>Trading Simulator Unavailable</h2>
      <p>The trading simulator is not running (Status: {simulatorStatus})</p>
      <p>Please start the simulator from the book details page.</p>
      <button 
        onClick={() => navigate(`/${simulationId}`)}
        style={{
          padding: '12px 24px',
          backgroundColor: '#00E5FF',
          color: '#0A2A36',
          border: 'none',
          borderRadius: '6px',
          fontSize: '16px',
          fontWeight: '500',
          cursor: 'pointer'
        }}
      >
        Return to Book Details
      </button>
    </div>
  );
};

export default SimulatorPage;