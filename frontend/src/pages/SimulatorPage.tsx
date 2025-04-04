import React from 'react';
import { useConnection } from '../contexts/ConnectionContext';
import './SimulatorPage.css';

const SimulatorPage: React.FC = () => {
  const { 
    isConnected, 
    connectionState, 
    startSimulator, 
    stopSimulator 
  } = useConnection();
  
  const handleStartSimulator = async () => {
    await startSimulator({});
  };

  const handleStopSimulator = async () => {
    await stopSimulator();
  };
  
  const isSimulatorRunning = connectionState.simulatorStatus === 'RUNNING';
  
  return (
    <div className="simulator-page">
      <div className="simulator-header">
        <h1>Trading Simulator</h1>
        <div className="simulator-controls">
          {isSimulatorRunning ? (
            <button 
              className="control-button stop-button" 
              onClick={handleStopSimulator}
              disabled={!isConnected || connectionState.simulatorStatus === 'STOPPING'}
            >
              Stop Simulator
            </button>
          ) : (
            <button 
              className="control-button start-button" 
              onClick={handleStartSimulator}
              disabled={!isConnected || connectionState.simulatorStatus === 'STARTING'}
            >
              Start Simulator
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default SimulatorPage;