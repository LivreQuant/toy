// src/pages/HomePage.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { useConnection } from '../hooks/useConnection';
import { useRequireAuth } from '../hooks/useRequireAuth';
import ConnectionStatusIndicator from '../components/Common/ConnectionStatusIndicator';
import { SimulationConfig } from '../types';
import './HomePage.css';

const HomePage: React.FC = () => {
  useRequireAuth();
  const { logout } = useAuth();
  const { connectionManager, connectionState, isConnected } = useConnection();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const [simulations, setSimulations] = useState<SimulationConfig[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch user's simulations
  useEffect(() => {
    // In a real implementation, this would call an API endpoint
    // For now, we'll just mock some data
    const mockSimulations: SimulationConfig[] = [
      {
        id: '1',
        name: 'Tech Sector Simulation',
        sector: 'Technology',
        riskLevel: 'medium',
        initialCapital: 100000,
        createdAt: Date.now() - 7 * 24 * 60 * 60 * 1000, // 7 days ago
        lastModified: Date.now() - 2 * 24 * 60 * 60 * 1000, // 2 days ago
        status: 'stopped'
      },
      {
        id: '2',
        name: 'Healthcare Portfolio',
        sector: 'Healthcare',
        riskLevel: 'low',
        initialCapital: 50000,
        createdAt: Date.now() - 14 * 24 * 60 * 60 * 1000, // 14 days ago
        lastModified: Date.now() - 1 * 24 * 60 * 60 * 1000, // 1 day ago
        status: 'configured'
      }
    ];
    
    setSimulations(mockSimulations);
    setIsLoading(false);
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
      addToast('error', `Logout failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  const handleCreateSimulation = () => {
    navigate('/simulation/new');
  };

  const handleStartSimulation = (simulation: SimulationConfig) => {
    // In a real implementation, this would call an API to start the simulation
    // Then navigate to the simulator page with the simulation ID
    navigate(`/simulator/${simulation.id}`);
  };

  const handleManualReconnect = () => {
    if (connectionManager) {
      connectionManager.manualReconnect();
      addToast('info', 'Attempting to reconnect...');
    }
  };

  return (
    <div className="home-page">
      {/* Header with Logout Button */}
      <header className="home-header">
        <h1>Trading Platform</h1>
        <button onClick={handleLogout} className="logout-button">
          Logout
        </button>
      </header>

      {/* Status Panel */}
      <div className="status-panel">
         <h2>Connection</h2>
         {connectionState ? (
             <ConnectionStatusIndicator
                state={connectionState}
                onManualReconnect={handleManualReconnect}
             />
         ) : (
            <p>Loading connection state...</p>
         )}
      </div>

      {/* Simulations Panel */}
      <div className="simulations-panel">
        <div className="panel-header">
          <h2>Your Simulations</h2>
          <button 
            onClick={handleCreateSimulation}
            className="create-button"
            disabled={!isConnected}
          >
            Initialize New Simulation
          </button>
        </div>
        
        {isLoading ? (
          <div className="loading-placeholder">Loading your simulations...</div>
        ) : simulations.length === 0 ? (
          <div className="empty-list">
            <p>You don't have any simulations yet.</p>
            <button 
              onClick={handleCreateSimulation}
              className="create-button-large"
              disabled={!isConnected}
            >
              Create Your First Simulation
            </button>
          </div>
        ) : (
          <div className="simulation-list">
            {simulations.map(sim => (
              <div key={sim.id} className="simulation-card">
                <div className="simulation-info">
                  <h3>{sim.name}</h3>
                  <div className="simulation-details">
                    <span className="detail">Sector: {sim.sector}</span>
                    <span className="detail">Risk: {sim.riskLevel}</span>
                    <span className="detail">Capital: ${sim.initialCapital.toLocaleString()}</span>
                  </div>
                  <div className="simulation-status">
                    Status: <span className={`status-${sim.status}`}>{sim.status}</span>
                  </div>
                </div>
                <div className="simulation-actions">
                  <button 
                    onClick={() => handleStartSimulation(sim)}
                    className="action-button start-button"
                    disabled={!isConnected || sim.status === 'running'}
                  >
                    {sim.status === 'running' ? 'Resume' : 'Start'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default HomePage;