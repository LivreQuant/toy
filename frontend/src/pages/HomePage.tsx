// src/pages/HomePage.tsx
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth'; // Import the useAuth hook
import { useConnection } from '../hooks/useConnection';
import { useRequireAuth } from '../hooks/useRequireAuth';
import ConnectionStatusIndicator from '../components/Common/ConnectionStatusIndicator';
import './HomePage.css';

const HomePage: React.FC = () => {
  useRequireAuth(); // Ensures user is authenticated to see this page
  // *** FIX: Removed 'user' from destructuring ***
  const { logout } = useAuth(); // Get logout function (user is not provided by default context)
  const { connectionManager, connectionState, isConnected } = useConnection();
  const navigate = useNavigate();

  // Example useEffect, keep if needed for other logic
  useEffect(() => {
    // Potential logic related to connectionManager on mount/unmount
  }, [connectionManager]);

  // Logout Handler Implementation
  const handleLogout = async () => {
    try {
      await logout();
      // Logout function in AuthContext should handle redirect
    } catch (error) {
      console.error('Logout failed:', error);
      // Consider adding a toast notification for error
    }
  };

  const handleGoToSimulator = () => {
    navigate('/simulator'); // Navigate to simulator page
  };

  // Manual Reconnect Handler Implementation
  const handleManualReconnect = () => {
    if (connectionManager) {
      connectionManager.manualReconnect();
      // Consider adding a toast notification
    }
  };

  return (
    <div className="home-page">
      {/* Header with Logout Button */}
      <header className="home-header">
        <h1>Home Page</h1>
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
                onManualReconnect={handleManualReconnect} // Pass handler
             />
         ) : (
            <p>Loading connection state...</p>
         )}
         {/* If you need user info, get it from AuthContext if added there
         {user && <p>Welcome, {user.username}!</p>}
         */}
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
      {/* Add other home page content here */}
    </div>
  );
};
export default HomePage;