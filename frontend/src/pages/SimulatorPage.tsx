import React, { useState, useEffect } from 'react';
import { useConnection } from '../contexts/ConnectionContext';
import MarketData from '../components/Simulator/MarketData';
import LoadingScreen from '../components/Common/LoadingScreen';
import './SimulatorPage.css';

const SimulatorPage: React.FC = () => {
  const { 
    isConnected, 
    connectionState, 
    startSimulator, 
    stopSimulator, 
    streamMarketData 
  } = useConnection();
  
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  
  useEffect(() => {
    if (isConnected && connectionState.simulatorStatus === 'RUNNING') {
      // Start streaming market data for some default symbols
      const defaultSymbols = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'FB'];
      streamMarketData(defaultSymbols).catch(err => {
        console.error('Failed to stream market data:', err);
      });
    }
  }, [isConnected, connectionState.simulatorStatus, streamMarketData]);
      
  const handleStartSimulator = async () => {
    setIsLoading(true);
    setStatusMessage('Starting simulator...');
    try {
      const result = await startSimulator({
        initialSymbols: ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'FB'],
        initialCash: 100000
      });
      
      if (result.success) {
        setStatusMessage('Simulator started successfully');
      } else {
        setStatusMessage(`Failed to start simulator: ${result.error}`);
      }
    } catch (error) {
      console.error('Failed to start simulator:', error);
      setStatusMessage('Error starting simulator');
    } finally {
      setIsLoading(false);
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  const handleStopSimulator = async () => {
    setIsLoading(true);
    setStatusMessage('Stopping simulator...');
    try {
      const result = await stopSimulator();
      
      if (result.success) {
        setStatusMessage('Simulator stopped successfully');
      } else {
        setStatusMessage(`Failed to stop simulator: ${result.error}`);
      }
    } catch (error) {
      console.error('Failed to stop simulator:', error);
      setStatusMessage('Error stopping simulator');
    } finally {
      setIsLoading(false);
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };
  
  const handleSymbolSelect = (symbol: string) => {
    setSelectedSymbol(symbol);
  };
  
  if (isLoading) {
    return <LoadingScreen message="Updating simulator state..." />;
  }
  
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
      
      <div className="simulator-content">
        <div className="market-data-section">
        </div>
        
        <div className="order-entry-section">
          <div className="order-entry-container">
            <h2 className="order-entry-title">Order Entry</h2>
            {selectedSymbol ? (
              <div className="order-form">
                <p>Create an order for: <strong>{selectedSymbol}</strong></p>
                {/* Placeholder for order entry form */}
                <div className="order-form-placeholder">
                  Order entry form will be implemented here
                </div>
              </div>
            ) : (
              <div className="no-symbol-selected">
                Select a symbol from the market data panel to place an order
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SimulatorPage;