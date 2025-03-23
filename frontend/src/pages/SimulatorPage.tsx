import React, { useState, useEffect } from 'react';
import { useConnection } from '../contexts/ConnectionContext';
import MarketData from '../components/Simulator/MarketData';
import LoadingScreen from '../components/Common/LoadingScreen';

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
    if (isConnected) {
      // Start streaming market data for some default symbols
      const defaultSymbols = ['AAPL', 'MSFT', 'AMZN', 'GOOGL', 'FB'];
      streamMarketData(defaultSymbols).catch(err => {
        console.error('Failed to stream market data:', err);
      });
    }
  }, [isConnected, streamMarketData]);
  
  const handleStartSimulator = async () => {
    setIsLoading(true);
    try {
      await startSimulator();
    } catch (error) {
      console.error('Failed to start simulator:', error);
    } finally {
      setIsLoading(false);
    }
  };
  
  const handleStopSimulator = async () => {
    setIsLoading(true);
    try {
      await stopSimulator();
    } catch (error) {
      console.error('Failed to stop simulator:', error);
    } finally {
      setIsLoading(false);
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
          <MarketData onSymbolSelect={handleSymbolSelect} />
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
      
      <style jsx>{`
        .simulator-page {
          padding: 20px;
          max-width: 1400px;
          margin: 0 auto;
        }
        
        .simulator-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }
        
        .control-button {
          padding: 10px 20px;
          border: none;
          border-radius: 4px;
          font-weight: bold;
          cursor: pointer;
          transition: background-color 0.2s;
        }
        
        .start-button {
          background-color: #2ecc71;
          color: white;
        }
        
        .start-button:hover:not([disabled]) {
          background-color: #27ae60;
        }
        
        .stop-button {
          background-color: #e74c3c;
          color: white;
        }
        
        .stop-button:hover:not([disabled]) {
          background-color: #c0392b;
        }
        
        .control-button[disabled] {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        .simulator-content {
          display: grid;
          grid-template-columns: 2fr 1fr;
          gap: 20px;
        }
        
        .order-entry-container {
          background-color: white;
          border-radius: 8px;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
          padding: 20px;
        }
        
        .order-entry-title {
          margin-top: 0;
          margin-bottom: 15px;
          font-size: 1.5rem;
          color: #333;
          border-bottom: 1px solid #eee;
          padding-bottom: 10px;
        }
        
        .no-symbol-selected {
          padding: 30px 20px;
          text-align: center;
          color: #666;
          background-color: #f9f9f9;
          border-radius: 6px;
          border: 1px dashed #ddd;
        }
        
        .order-form-placeholder {
          padding: 20px;
          background-color: #f8f9fa;
          border: 1px dashed #ccc;
          border-radius: 5px;
          text-align: center;
          color: #666;
          margin-top: 20px;
        }
        
        @media (max-width: 900px) {
          .simulator-content {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};

export default SimulatorPage;