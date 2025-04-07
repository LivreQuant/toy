// src/pages/HomePage.tsx (Corrected State Access)
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useConnection } from '../hooks/useConnection'; // Imports useConnection hook
import { useRequireAuth } from '../hooks/useRequireAuth';
import ConnectionStatusIndicator from '../components/Common/ConnectionStatusIndicator';
import './HomePage.css';

const HomePage: React.FC = () => {
  useRequireAuth();
  const { logout } = useAuth();
  // Destructure isConnected directly from the hook's return value
  const { connectionManager, connectionState, isConnected } = useConnection();
  const navigate = useNavigate();

  useEffect(() => { /* ... */ }, [connectionManager]);
  const handleLogout = async () => { /* ... */ };
  const handleGoToSimulator = () => { /* ... */ };
  const handleManualReconnect = () => { /* ... */ };

  return (
    <div className="home-page">
      {/* ... (header) ... */}
      <div className="status-panel">
         <h2>Connection</h2>
         {/* Pass connectionState slice which is AppState['connection'] */}
         {connectionState && (
             <ConnectionStatusIndicator
                state={connectionState}
                onManualReconnect={handleManualReconnect}
             />
         )}
         {!connectionState && <p>Loading connection state...</p>}
      </div>
      <div className="action-panel">
        <h2>Actions</h2>
        <div className="action-buttons">
            <button
                onClick={handleGoToSimulator}
                className="action-button"
                // Use isConnected directly from useConnection()
                disabled={!isConnected}
                title={!isConnected ? "Connect first to use the simulator" : ""}
            >
               <span className="action-icon">📈</span>
               <span>Trading Simulator</span>
            </button>
        </div>
      </div>
    </div>
  );
};
export default HomePage;