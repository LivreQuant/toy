// src/pages/SimulatorPage.tsx (updated)
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom'; // Add useParams
import { useConnection } from '../hooks/useConnection';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useToast } from '../hooks/useToast';
import ConnectionStatusIndicator from '../components/Common/ConnectionStatusIndicator';
import CsvOrderUpload from '../components/Simulator/CsvOrderUpload';
import { SimulationConfig } from '../types/simulation'; // Import the type
import './SimulatorPage.css';

const SimulatorPage: React.FC = () => {
  useRequireAuth();
  const { simulationId } = useParams<{ simulationId: string }>(); // Get the simulation ID from the URL
  const { connectionManager, connectionState, isConnected } = useConnection();
  const { addToast } = useToast();
  const navigate = useNavigate();
  
  // Add state for the simulation
  const [simulation, setSimulation] = useState<SimulationConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Local state for button disabling during API calls
  const [isSimActionLoading, setIsSimActionLoading] = useState(false);

  // Load the simulation data
  useEffect(() => {
    const loadSimulation = async () => {
      // In a real implementation, this would call an API to load the simulation
      // For now, we'll just mock it
      try {
        // Simulate API call delay
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Mock simulation data
        const mockSimulation: SimulationConfig = {
          id: simulationId || '0',
          name: 'Tech Sector Simulation',
          sector: 'Technology',
          riskLevel: 'medium',
          initialCapital: 100000,
          createdAt: Date.now() - 7 * 24 * 60 * 60 * 1000,
          lastModified: Date.now() - 2 * 24 * 60 * 60 * 1000,
          status: 'configured'
        };
        
        setSimulation(mockSimulation);
      } catch (error) {
        addToast('error', `Failed to load simulation: ${error instanceof Error ? error.message : 'Unknown error'}`);
      } finally {
        setIsLoading(false);
      }
    };
    
    loadSimulation();
  }, [simulationId, addToast]);

  // Derived state from context
  const simulatorStatus = connectionState?.simulatorStatus || 'UNKNOWN';
  const isSimulatorRunning = simulatorStatus === 'RUNNING';
  const isSimulatorBusy = simulatorStatus === 'STARTING' || simulatorStatus === 'STOPPING';

  // Handler to attempt stopping the simulator
  const handleStopSimulator = useCallback(async () => {
      if (!connectionManager || isSimulatorBusy || !isSimulatorRunning) return false;
      setIsSimActionLoading(true);
      addToast('info', 'Attempting to stop simulator...');
      let success = false;
      try {
           const result = await connectionManager.stopSimulator();
           if (result.success) {
               addToast('success', `Simulator stopped (Status: ${result.status || 'STOPPED'})`);
               
               // In a real implementation, update the simulation status in your state and backend
               if (simulation) {
                 setSimulation({
                   ...simulation,
                   status: 'stopped'
                 });
               }
               
               success = true;
           } else {
               addToast('error', `Failed to stop simulator: ${result.error || 'Unknown reason'}`);
           }
       } catch (error: any) {
           addToast('error', `Error stopping simulator: ${error.message}`);
       } finally {
          setIsSimActionLoading(false);
       }
       return success;
   }, [connectionManager, isSimulatorBusy, isSimulatorRunning, addToast, simulation]);

   // Handler to Stop Simulator and Go Home
   const handleShutdownAndGoHome = useCallback(async () => {
        if (isSimulatorBusy || !isSimulatorRunning) return;
        const stopped = await handleStopSimulator();
        navigate('/home');
   }, [handleStopSimulator, navigate, isSimulatorBusy, isSimulatorRunning]);

   const handleStartSimulator = useCallback(async () => {
      if (!connectionManager || isSimulatorBusy || isSimulatorRunning) return;
      setIsSimActionLoading(true);
      addToast('info', 'Attempting to start simulator...');
      try {
          const result = await connectionManager.startSimulator();
          if (result.success) {
              addToast('success', `Simulator started (Status: ${result.status || 'RUNNING'})`);
              
              // In a real implementation, update the simulation status in your state and backend
              if (simulation) {
                setSimulation({
                  ...simulation,
                  status: 'running' 
                });
              }
          } else {
              addToast('error', `Failed to start simulator: ${result.error || 'Unknown reason'}`);
          }
      } catch (error: any) {
          addToast('error', `Error starting simulator: ${error.message}`);
      } finally {
         setIsSimActionLoading(false);
      }
   }, [connectionManager, isSimulatorBusy, isSimulatorRunning, addToast, simulation]);

   const handleGoBack = useCallback(() => {
       navigate('/home');
   }, [navigate]);

   const handleManualReconnect = useCallback(() => {
       if (connectionManager) {
           addToast('info', 'Attempting manual reconnect...');
           connectionManager.manualReconnect();
       }
   }, [connectionManager, addToast]);

  if (isLoading) {
    return <div className="loading-container">Loading simulation data...</div>;
  }

  if (!simulation) {
    return <div className="error-container">Simulation not found.</div>;
  }

  return (
    <div className="simulator-page">
        <header className="simulator-header">
            <h1>{simulation.name}</h1>
            <div className="simulator-info">
              <span className="info-item">Sector: {simulation.sector}</span>
              <span className="info-item">Risk Level: {simulation.riskLevel}</span>
              <span className="info-item">Capital: ${simulation.initialCapital.toLocaleString()}</span>
            </div>
            <div className="simulator-controls">
                {/* Back button */}
                <button onClick={handleGoBack} className="control-button secondary">Back</button>

                {/* Start Button */}
                <button
                    onClick={handleStartSimulator}
                    disabled={!isConnected || isSimulatorRunning || isSimulatorBusy || isSimActionLoading}
                    className="control-button start-button"
                >
                   {simulatorStatus === 'STARTING' ? 'Starting...' : 'Start Simulator'}
                </button>

                {/* Shutdown and Go Home Button */}
                <button
                    onClick={handleShutdownAndGoHome}
                    disabled={!isConnected || !isSimulatorRunning || isSimulatorBusy || isSimActionLoading}
                    className="control-button danger"
                    title="Stop simulator and return to home"
                >
                   {simulatorStatus === 'STOPPING' ? 'Stopping...' : 'Shutdown & Home'}
                </button>
            </div>
        </header>

        {connectionState ? (
            <ConnectionStatusIndicator
                state={connectionState}
                onManualReconnect={handleManualReconnect}
            />
        ) : (
            <p>Loading connection state...</p>
        )}

        <div className="simulator-content">
            <div className="order-entry-container">
                <h2 className="order-entry-title">Order Management</h2>
                {isConnected && isSimulatorRunning ? (
                    <CsvOrderUpload />
                ) : (
                    <div className="order-form-placeholder">
                        <p>
                        {!isConnected ? "Waiting for connection..." : "Simulator not running. Start the simulator to manage orders."}
                        </p>
                    </div>
                )}
            </div>
        </div>
    </div>
  );
};

export default SimulatorPage;