// src/pages/HomePage.tsx
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { useConnection } from '../hooks/useConnection';
import { useRequireAuth } from '../hooks/useRequireAuth';
import ConnectionStatusIndicator from '../components/Common/ConnectionStatusIndicator';
import CsvOrderUpload from '../components/Simulator/CsvOrderUpload'; // Add this import
import './HomePage.css';

const HomePage: React.FC = () => {
  useRequireAuth();
  const { logout } = useAuth();
  const { connectionManager, connectionState, isConnected } = useConnection();
  const { addToast } = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    // Potential logic related to connectionManager on mount/unmount
  }, [connectionManager]);

  const handleLogout = async () => {
    try {
      await logout();
      // Logout function in AuthContext should handle redirect
    } catch (error) {
      console.error('Logout failed:', error);
      // Add toast notification
      addToast('error', `Logout failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  const handleGoToSimulator = () => {
    navigate('/simulator');
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

      {/* Order Management Panel - Always visible for authenticated users */}
      <div className="order-panel">
        <h2>Order Management</h2>
        <CsvOrderUpload />
      </div>

      {/* Action Panel */}
      <div className="action-panel">
        <h2>Actions</h2>
        <div className="action-buttons">
            <button
                onClick={handleGoToSimulator}
                className="action-button"
                disabled={!isConnected}
                title={!isConnected ? "Connect first to use the simulator" : ""}
            >
               <span className="action-icon">📈</span>
               <span>Trading Simulator</span>
            </button>
            {/* Add other action buttons here */}
        </div>
      </div>
    </div>
  );
};
export default HomePage;