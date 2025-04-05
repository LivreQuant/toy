// src/pages/SimulatorPage.tsx
import React from 'react';
// Import the hook to use the connection context
import { useConnection } from '../contexts/ConnectionContext'; // Adjust path if needed
// Import status enum if needed for explicit checks
import { ConnectionStatus } from '../services/connection/unified-connection-state'; // Adjust path
import './SimulatorPage.css';
import { toastService } from '../services/notification/toast-service'; // For user feedback

const SimulatorPage: React.FC = () => {
  // --- Refactored: Destructure state and actions correctly from the updated context ---
  const {
    isConnected,      // Boolean flag: Is primary connection (WebSocket) established?
    isConnecting,     // Boolean flag: Is primary connection attempt in progress?
    isRecovering,     // Boolean flag: Is primary connection recovery in progress?
    overallStatus,    // Overall connection status enum (CONNECTED, DISCONNECTED, etc.)
    startSimulator,   // Function to start the simulator via ConnectionManager
    stopSimulator,    // Function to stop the simulator via ConnectionManager
    simulatorStatus   // Current status string of the simulator (e.g., RUNNING, STOPPED)
  } = useConnection();

  // --- Derived State ---
  // Determine if the simulator is considered running
  const isRunning = simulatorStatus === 'RUNNING';
  // Determine if the simulator is in a transient state (starting/stopping)
  const isBusy = simulatorStatus === 'STARTING' || simulatorStatus === 'STOPPING';
  // Determine if controls should be disabled (not connected, connecting, recovering, or simulator busy)
  const controlsDisabled = !isConnected || isConnecting || isRecovering || isBusy;

  // --- Event Handlers ---
  const handleStartSimulator = async () => {
    // Prevent action if controls should be disabled or simulator is already running
    if (controlsDisabled || isRunning) return;

    toastService.info("Attempting to start simulator...");
    try {
        const result = await startSimulator(); // Call action from context
        if (result.success) {
            toastService.success(`Simulator started successfully. Status: ${result.status}`);
            // State update should come via context subscription, no need to set locally
        } else {
            toastService.error(`Failed to start simulator: ${result.error || 'Unknown error'}`);
        }
    } catch (error: any) {
        console.error("Error starting simulator:", error);
        toastService.error(`Error starting simulator: ${error.message}`);
    }
  };

  const handleStopSimulator = async () => {
    // Prevent action if controls should be disabled or simulator is not running
    if (controlsDisabled || !isRunning) return;

    toastService.info("Attempting to stop simulator...");
     try {
        const result = await stopSimulator(); // Call action from context
        if (result.success) {
            toastService.success("Simulator stopped successfully.");
            // State update should come via context subscription
        } else {
            toastService.error(`Failed to stop simulator: ${result.error || 'Unknown error'}`);
        }
    } catch (error: any) {
        console.error("Error stopping simulator:", error);
        toastService.error(`Error stopping simulator: ${error.message}`);
    }
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
            // Disable if controls should be disabled OR if the simulator is already running
            disabled={controlsDisabled || isRunning}
            title={controlsDisabled ? "Cannot start simulator while disconnected or busy" : isRunning ? "Simulator is already running" : "Start the simulator"}
          >
            Start Simulator
          </button>
          {/* Stop Simulator Button */}
          <button
            className="control-button stop-button"
            onClick={handleStopSimulator}
            // Disable if controls should be disabled OR if the simulator is not running
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
