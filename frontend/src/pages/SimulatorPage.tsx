// src/pages/SimulatorPage.tsx
import React, { useEffect, useState, useCallback } from 'react'; // Added useCallback
import { useNavigate } from 'react-router-dom';
import { useConnection } from '../hooks/useConnection';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useToast } from '../hooks/useToast';
import OrderEntryForm from '../components/Simulator/OrderEntryForm';
import ConnectionStatusIndicator from '../components/Common/ConnectionStatusIndicator';
import './SimulatorPage.css';
// Assuming ConnectionStatus exists and is needed, if not remove it
// import { ConnectionStatus } from '../services/state/app-state.service';

const SimulatorPage: React.FC = () => {
  useRequireAuth();
  const { connectionManager, connectionState, isConnected } = useConnection();
  const { addToast } = useToast();
  const navigate = useNavigate();

  // Local state for button disabling during API calls
  const [isSimActionLoading, setIsSimActionLoading] = useState(false);

  // Derived state from context
  const simulatorStatus = connectionState?.simulatorStatus || 'UNKNOWN';
  const isSimulatorRunning = simulatorStatus === 'RUNNING';
  const isSimulatorBusy = simulatorStatus === 'STARTING' || simulatorStatus === 'STOPPING';

  // Set desired state on mount/unmount (optional, depends on desired behavior)
  // useEffect(() => {
  //    // Indicate desire to be connected when entering the page
  //    if (connectionManager) {
  //       connectionManager.setDesiredState({ connected: true });
  //    }
  //    // Clean up: Optionally set desired state to disconnected on unmount?
  //    // return () => {
  //    //    if (connectionManager) {
  //    //       // connectionManager.setDesiredState({ connected: false }); // Or keep connected?
  //    //    }
  //    // };
  // }, [connectionManager]);


  const handleStartSimulator = useCallback(async () => {
      if (!connectionManager || isSimulatorBusy || isSimulatorRunning) return;
      setIsSimActionLoading(true);
      addToast('info', 'Attempting to start simulator...');
      try {
          const result = await connectionManager.startSimulator();
          if (result.success) {
              addToast('success', `Simulator started (Status: ${result.status || 'RUNNING'})`);
          } else {
              addToast('error', `Failed to start simulator: ${result.error || 'Unknown reason'}`);
          }
      } catch (error: any) {
          addToast('error', `Error starting simulator: ${error.message}`);
      } finally {
         setIsSimActionLoading(false);
      }
   }, [connectionManager, isSimulatorBusy, isSimulatorRunning, addToast]);

   const handleStopSimulator = useCallback(async () => {
      if (!connectionManager || isSimulatorBusy || !isSimulatorRunning) return;
      setIsSimActionLoading(true);
       addToast('info', 'Attempting to stop simulator...');
      try {
           const result = await connectionManager.stopSimulator();
           if (result.success) {
               addToast('success', `Simulator stopped (Status: ${result.status || 'STOPPED'})`);
           } else {
               addToast('error', `Failed to stop simulator: ${result.error || 'Unknown reason'}`);
           }
       } catch (error: any) {
           addToast('error', `Error stopping simulator: ${error.message}`);
       } finally {
          setIsSimActionLoading(false);
       }
   }, [connectionManager, isSimulatorBusy, isSimulatorRunning, addToast]);

   const handleGoBack = useCallback(() => {
       navigate(-1); // Navigate back to the previous page
   }, [navigate]);

   const handleManualReconnect = useCallback(() => {
       if (connectionManager) {
           addToast('info', 'Attempting manual reconnect...');
           connectionManager.manualReconnect();
       }
   }, [connectionManager, addToast]);


  return (
    <div className="simulator-page">
        <header className="simulator-header">
            <h1>Trading Simulator</h1>
            <div className="simulator-controls">
                <button onClick={handleGoBack} className="control-button secondary">Back</button>
                <button
                    onClick={handleStartSimulator}
                    disabled={!isConnected || isSimulatorRunning || isSimulatorBusy || isSimActionLoading}
                    className="control-button start-button"
                >
                   {simulatorStatus === 'STARTING' ? 'Starting...' : 'Start Simulator'}
                </button>
                <button
                    onClick={handleStopSimulator}
                    disabled={!isConnected || !isSimulatorRunning || isSimulatorBusy || isSimActionLoading}
                    className="control-button stop-button"
                >
                   {simulatorStatus === 'STOPPING' ? 'Stopping...' : 'Stop Simulator'}
                </button>
            </div>
        </header>

         {/* Pass connectionState slice only if it exists */}
         {connectionState && (
            <ConnectionStatusIndicator
                state={connectionState}
                onManualReconnect={handleManualReconnect}
            />
         )}

        <div className="simulator-content">
             <div className="market-data-container">
                 <h2>Market Data / Charts</h2>
                 {/* FIX: Removed erroneous '>' after comment */}
                 {/* FIX: Corrected JSX Structure */}
                 {isConnected && isSimulatorRunning ? (
                    <div> {/* Replace with actual Market Data component */}
                        <p>Market Data/Charts Area (Connected & Simulator Running)</p>
                    </div>
                 ) : (
                    <div className="market-data-placeholder">
                       <p>
                       { !isConnected ? "Waiting for connection..." : "Simulator not running. Start the simulator to view market data." }
                       </p>
                    </div>
                 )}
             </div>
             <div className="order-entry-container">
                 <h2 className="order-entry-title">Order Entry</h2>
                 {/* Use derived state directly */}
                 {isConnected && isSimulatorRunning ? (
                    <OrderEntryForm />
                 ) : (
                    <div className="order-form-placeholder">
                       <p>
                       { !isConnected ? "Waiting for connection..." : "Simulator not running. Start the simulator to place orders." }
                       </p>
                    </div>
                 )}
             </div>
        </div>
        {/* FIX: Removed extra closing div that likely caused TS2304/TS1005 etc. */}
    </div> // This corresponds to the opening div with className="simulator-page"
  );
};

export default SimulatorPage;