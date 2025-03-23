// src/pages/HomePage.tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { validateToken, logout } from '../services/grpc/auth';
import { createSession } from '../services/grpc/session';
import { startSimulator, stopSimulator, getSimulatorStatus } from '../services/grpc/simulator';
import { SimulatorStatus } from '../types/simulator';

const HomePage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [simulatorId, setSimulatorId] = useState<string | null>(null);
  const [simulatorStatus, setSimulatorStatus] = useState<SimulatorStatus>('UNKNOWN');
  const navigate = useNavigate();
  
  // Get token from localStorage
  const token = localStorage.getItem('token');
  
  useEffect(() => {
    // Redirect to login if no token
    if (!token) {
      navigate('/login');
      return;
    }
    
    // Validate token and create session
    const init = async () => {
      try {
        setLoading(true);
        
        // Validate token
        const validationResponse = await validateToken(token);
        if (!validationResponse.valid) {
          localStorage.removeItem('token');
          navigate('/login');
          return;
        }
        
        // Create session
        const sessionResponse = await createSession(token);
        if (sessionResponse.success) {
          setSessionId(sessionResponse.sessionId);
          
          // Check if we have a simulator ID in localStorage
          const storedSimulatorId = localStorage.getItem('simulatorId');
          if (storedSimulatorId) {
            setSimulatorId(storedSimulatorId);
            
            // Get simulator status
            const statusResponse = await getSimulatorStatus(token, storedSimulatorId);
            setSimulatorStatus(statusResponse.status);
          }
        } else {
          setError(sessionResponse.errorMessage || 'Failed to create session');
        }
      } catch (err) {
        setError('Connection error. Please try again.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    
    init();
    
    // Set up status polling if we have a simulator
    const statusInterval = setInterval(async () => {
      if (simulatorId && token) {
        try {
          const statusResponse = await getSimulatorStatus(token, simulatorId);
          setSimulatorStatus(statusResponse.status);
        } catch (err) {
          console.error('Failed to get simulator status:', err);
        }
      }
    }, 5000); // Poll every 5 seconds
    
    return () => {
      clearInterval(statusInterval);
    };
  }, [token, navigate, simulatorId]);
  
  const handleStartSimulator = async () => {
    if (!token || !sessionId) return;
    
    try {
      setLoading(true);
      
      const response = await startSimulator(token, sessionId);
      if (response.success) {
        setSimulatorId(response.simulatorId);
        setSimulatorStatus('STARTING');
        
        // Store simulator ID in localStorage
        localStorage.setItem('simulatorId', response.simulatorId);
        
        // Navigate to simulator page
        navigate('/simulator');
      } else {
        setError(response.errorMessage || 'Failed to start simulator');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleStopSimulator = async () => {
    if (!token || !simulatorId) return;
    
    try {
      setLoading(true);
      
      const response = await stopSimulator(token, simulatorId);
      if (response.success) {
        setSimulatorStatus('STOPPING');
        
        // Poll status until stopped
        const checkStatus = async () => {
          const statusResponse = await getSimulatorStatus(token, simulatorId);
          if (statusResponse.status === 'STOPPED') {
            setSimulatorId(null);
            localStorage.removeItem('simulatorId');
          } else if (statusResponse.status !== 'STOPPING') {
            // If not stopping or stopped, simulator is gone
            setSimulatorId(null);
            localStorage.removeItem('simulatorId');
          } else {
            // Still stopping, check again in 1 second
            setTimeout(checkStatus, 1000);
          }
        };
        
        checkStatus();
      } else {
        setError(response.errorMessage || 'Failed to stop simulator');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };
  
  const handleLogout = async () => {
    if (!token) return;
    
    // Stop simulator if running
    if (simulatorId) {
      await handleStopSimulator();
    }
    
    try {
      await logout(token);
    } catch (err) {
      console.error('Error during logout:', err);
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('simulatorId');
      navigate('/login');
    }
  };
  
  if (loading && !sessionId) {
    return <div>Loading...</div>;
  }
  
  return (
    <div className="home-container">
      <h1>Trading Exchange Simulator</h1>
      
      <div className="simulator-controls">
        <h2>Exchange Simulator</h2>
        
        {error && <div className="error-message">{error}</div>}
        
        <div className="status-display">
          <strong>Status:</strong> {simulatorStatus}
        </div>
        
        <div className="button-group">
          {(!simulatorId || simulatorStatus === 'STOPPED') && (
            <button onClick={handleStartSimulator} disabled={loading}>
              Start Simulator
            </button>
          )}
          
          {simulatorId && simulatorStatus === 'RUNNING' && (
            <>
              <button onClick={() => navigate('/simulator')}>
                Open Simulator
              </button>
              
              <button onClick={handleStopSimulator} disabled={loading}>
                Stop Simulator
              </button>
            </>
          )}
        </div>
      </div>
      
      <button className="logout-button" onClick={handleLogout}>
        Logout
      </button>
    </div>
  );
};

export default HomePage;