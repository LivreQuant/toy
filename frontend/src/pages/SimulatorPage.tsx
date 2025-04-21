// src/pages/SimulatorPage.tsx
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useConnection } from '../hooks/useConnection';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useToast } from '../hooks/useToast';
import OrderEntryForm from '../components/Simulator/OrderEntryForm'; // Assuming component exists
import ConnectionStatusIndicator from '../components/Common/ConnectionStatusIndicator'; // Assuming component exists
import './SimulatorPage.css';

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

  // Handler to attempt stopping the simulator
  const handleStopSimulator = useCallback(async () => {
      if (!connectionManager || isSimulatorBusy || !isSimulatorRunning) return false; // Return success status
      setIsSimActionLoading(true);
       addToast('info', 'Attempting to stop simulator...');
      let success = false; // Track success
      try {
           const result = await connectionManager.stopSimulator();
           if (result.success) {
               addToast('success', `Simulator stopped (Status: ${result.status || 'STOPPED'})`);
               success = true; // Mark as successful
           } else {
               addToast('error', `Failed to stop simulator: ${result.error || 'Unknown reason'}`);
           }
       } catch (error: any) {
           addToast('error', `Error stopping simulator: ${error.message}`);
       } finally {
          setIsSimActionLoading(false);
       }
       return success; // Return success status
   }, [connectionManager, isSimulatorBusy, isSimulatorRunning, addToast]);

    useEffect(() => {
        console.log("Simulator status changed:", {
        simulatorStatus,
        isSimulatorRunning,
        isSimulatorBusy,
        isConnected
        });
    }, [simulatorStatus, isSimulatorRunning, isSimulatorBusy, isConnected]);

   // --- NEW: Handler to Stop Simulator and Go Home ---
   const handleShutdownAndGoHome = useCallback(async () => {
        // Prevent action if already busy or not running
        if (isSimulatorBusy || !isSimulatorRunning) return;

        const stopped = await handleStopSimulator(); // Call existing stop logic

        // Navigate home regardless of whether stop succeeded,
        // or only navigate on success? Your choice.
        // This example navigates regardless.
        // if (stopped) { // Uncomment this line to only navigate if stop was successful
             navigate('/home');
        // }
   }, [handleStopSimulator, navigate, isSimulatorBusy, isSimulatorRunning]);
   // --- End New Handler ---

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

   const handleGoBack = useCallback(() => {
       // Consider stopping the simulator if user navigates back? Optional.
       // if (isSimulatorRunning) { handleStopSimulator(); }
       navigate(-1); // Navigate back to the previous page (likely HomePage)
   }, [navigate /*, isSimulatorRunning, handleStopSimulator */]); // Add dependencies if uncommenting stop logic

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
                {/* Back button remains */}
                <button onClick={handleGoBack} className="control-button secondary">Back</button>

                {/* Start Button */}
                <button
                    onClick={handleStartSimulator}
                    disabled={!isConnected || isSimulatorRunning || isSimulatorBusy || isSimActionLoading}
                    className="control-button start-button"
                >
                   {simulatorStatus === 'STARTING' ? 'Starting...' : 'Start Simulator'}
                </button>

                {/* --- NEW: Shutdown and Go Home Button --- */}
                <button
                    onClick={handleShutdownAndGoHome} // Use new handler
                    disabled={!isConnected || !isSimulatorRunning || isSimulatorBusy || isSimActionLoading} // Similar disabled logic to stop
                    className="control-button danger" // Use danger style or create a specific one
                    title="Stop simulator and return to home"
                >
                   {simulatorStatus === 'STOPPING' ? 'Stopping...' : 'Shutdown & Home'}
                </button>
                 {/* You might want to keep the original Stop button or remove it */}
                 {/*
                 <button
                     onClick={handleStopSimulator}
                     disabled={!isConnected || !isSimulatorRunning || isSimulatorBusy || isSimActionLoading}
                     className="control-button stop-button"
                 >
                    {simulatorStatus === 'STOPPING' ? 'Stopping...' : 'Stop Simulator'}
                 </button>
                 */}
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
             <div className="market-data-container">
                 <h2>Market Data / Charts</h2>
                 {isConnected && isSimulatorRunning ? (
                    <div>
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
    </div>
  );
};

export default SimulatorPage;