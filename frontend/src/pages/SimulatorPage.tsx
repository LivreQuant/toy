// src/pages/SimulatorPage.tsx (Corrected State Access & Logic)
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
// Import useConnection hook
import { useConnection } from '../hooks/useConnection';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useToast } from '../hooks/useToast';
import OrderEntryForm from '../components/Simulator/OrderEntryForm';
import ConnectionStatusIndicator from '../components/Common/ConnectionStatusIndicator';
import './SimulatorPage.css';

const SimulatorPage: React.FC = () => {
  useRequireAuth();
  // Destructure needed state/methods directly from useConnection
  const { connectionManager, connectionState, isConnected } = useConnection();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  // Get simulator status from the connectionState object
  const simulatorStatus = connectionState?.simulatorStatus || 'UNKNOWN';
  const isSimulatorRunning = simulatorStatus === 'RUNNING';
  // Simplify busy check
  const isSimulatorBusy = simulatorStatus === 'STARTING' || simulatorStatus === 'STOPPING';


  useEffect(() => { /* ... */ }, [connectionManager]);
  const handleStartSimulator = async () => { /* ... */ };
  const handleStopSimulator = async () => { /* ... */ };
  const handleGoBack = () => { /* ... */ };
  const handleManualReconnect = () => { /* ... */ };

  return (
    <div className="simulator-page">
        <header className="simulator-header">
            <h1>Trading Simulator</h1>
            <div className="simulator-controls"> {/* Added wrapper div */}
                <button onClick={handleGoBack} className="control-button secondary">Back</button> {/* Added class */}
                <button
                    onClick={handleStartSimulator}
                    // Use isConnected directly, use isSimulatorBusy
                    disabled={!isConnected || isSimulatorRunning || isSimulatorBusy}
                    className="control-button start-button"
                >
                   {/* Use isSimulatorBusy for label */}
                   {simulatorStatus === 'STARTING' ? 'Starting...' : 'Start Simulator'}
                </button>
                <button
                    onClick={handleStopSimulator}
                    // Use isConnected directly, use isSimulatorBusy, simplify check
                    disabled={!isConnected || !isSimulatorRunning || isSimulatorBusy}
                    className="control-button stop-button"
                >
                   {/* Use isSimulatorBusy for label */}
                   {simulatorStatus === 'STOPPING' ? 'Stopping...' : 'Stop Simulator'}
                </button>
            </div>
        </header>
         {/* Pass connectionState slice */}
         {connectionState && ( <ConnectionStatusIndicator state={connectionState} onManualReconnect={handleManualReconnect} /> )}
        <div className="simulator-content">
            {/* ... (market data/order entry sections) ... */}
             <div className="market-data-container">
                 <h2>Market Data / Charts</h2>
                 {/* Use isConnected directly */}
                 {isConnected && isSimulatorRunning ? ( /* ... */ ) : ( <div className="market-data-placeholder"> /* ... */ </div> )}
             </div>
             <div className="order-entry-container">
                 <h2 className="order-entry-title">Order Entry</h2>
                 {/* Use isConnected directly */}
                 {isConnected && isSimulatorRunning ? ( <OrderEntryForm /> ) : ( <div className="order-form-placeholder"> /* ... */ </div> )}
             </div>
        </div>
    </div>
  );
};
export default SimulatorPage;