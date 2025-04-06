// src/pages/SimulatorPage.tsx
import React, { useEffect } from 'react';
// Import the hook to use the connection context
import { useConnection } from '../contexts/ConnectionContext'; 
// Import ConnectionStatus for explicit checks
import { ConnectionStatus } from '../services/connection/unified-connection-state'; 
import './SimulatorPage.css';

const SimulatorPage: React.FC = () => {
  // --- Destructure state and actions using the updated context ---
  const {
    isConnected,      // Boolean flag: Is connection established?
    isConnecting,     // Boolean flag: Is connection attempt in progress?
    isRecovering,     // Boolean flag: Is connection recovery in progress?
    overallStatus,    // Overall connection status enum
    simulatorStatus,  // Current status string of the simulator
    setDesiredState   // New declarative API method
  } = useConnection();

  // --- Derived State ---
  // Determine if the simulator is considered running
  const isRunning = simulatorStatus === 'RUNNING';
  // Determine if the simulator is in a transient state (starting/stopping)
  const isBusy = simulatorStatus === 'STARTING' || simulatorStatus === 'STOPPING';
  // Determine if controls should be disabled
  const controlsDisabled = !isConnected || isConnecting || isRecovering || isBusy;

  // Connect on mount (alternative to the automatic approach)
  useEffect(() => {
    // If not connected or connecting, set desired state to connected
    if (overallStatus === ConnectionStatus.DISCONNECTED) {
      setDesiredState({ connected: true });
    }
  }, [overallStatus, setDesiredState]);

  // --- Event Handlers ---
  // Declarative handlers that update desired state
  const handleStartSimulator = () => {
    // Set the desired state for the simulator to be running
    setDesiredState({ simulatorRunning: true });
  };

  const handleStopSimulator = () => {
    // Set the desired state for the simulator to be stopped
    setDesiredState({ simulatorRunning: false });
  };

  return (
    <div className="simulator-page">
      <div className="simulator-header">
        <h2>Simulator Control</h2>
        <div>
          {/* Start Simulator Button */}
          <button
            className="control-button start-button"
            onClick={handleStartSimulator}
            disabled={controlsDisabled || isRunning}
            title={controlsDisabled ? "Cannot start simulator while disconnected or busy" : isRunning ? "Simulator is already running" : "Start the simulator"}
          >
            Start Simulator
          </button>
          {/* Stop Simulator Button */}
          <button
            className="control-button stop-button"
            onClick={handleStopSimulator}
            disabled={controlsDisabled || !isRunning}
            title={controlsDisabled ? "Cannot stop simulator while disconnected or busy" : !isRunning ? "Simulator is not running" : "Stop the simulator"}
          >
            Stop Simulator
          </button>
        </div>
      </div>

      {/* Display Status Information */}
      <div className="status-panel">
         <p>Connection Status: <strong>{overallStatus}</strong></p>
         <p>Simulator Status: <strong>{simulatorStatus || 'N/A'}</strong></p>
         {!isConnected && <p style={{color: 'red'}}>Warning: Controls disabled while disconnected.</p>}
         {isBusy && <p style={{color: 'orange'}}>Simulator is currently {simulatorStatus?.toLowerCase()}...</p>}
      </div>

      {/* Placeholder for Order Entry/Other Simulator Components */}
      <div className="simulator-content">
          <div className="order-entry-container">
              <h3 className="order-entry-title">Order Entry</h3>
              {isConnected ? (
                  <div className="order-form-placeholder">
                      Order form components would go here.
                      (Requires connection to be active)
                  </div>
              ) : (
                  <div className="no-symbol-selected">
                      Connect to the server to enable order entry.
                  </div>
              )}
          </div>
          {/* Add other simulator related components here */}
      </div>
    </div>
  );
};

export default SimulatorPage;