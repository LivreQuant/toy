// src/pages/HomePage.tsx
import React from 'react';
// Import the hook to use the connection context
import { useConnection } from '../contexts/ConnectionContext'; // Adjust path if needed
// Import the hook for authentication actions
import { useAuth } from '../contexts/AuthContext'; // Adjust path if needed
import './HomePage.css';

const HomePage: React.FC = () => {
  // --- Refactored: Destructure properties correctly from context ---
  // Get connection status details.
  const {
    isConnected,      // Simple boolean flag for connected status
    overallStatus,    // Enum value (CONNECTED, DISCONNECTED, etc.)
    connectionQuality // Quality enum value
  } = useConnection();

  // Get the logout function from the authentication context.
  const { logout } = useAuth();

  // --- Event Handler for Logout ---
  const handleLogout = async () => {
    try {
      await logout();
      // Optional: Add redirection logic after logout if needed
      // e.g., history.push('/login');
    } catch (error) {
      console.error("Logout failed:", error);
      // Optionally show a toast notification on logout failure
    }
  };

  return (
    <div className="home-page">
      <div className="home-header">
        <h1>Dashboard</h1>
        <button onClick={handleLogout} className="logout-button">Logout</button>
      </div>

      {/* Display connection status information */}
      <div className="status-panel">
        <h2>System Status</h2>
        <div className="status-grid">
           <div className="status-item">
              <div className="status-label">Connection</div>
              {/* Display more user-friendly status text */}
              <div className={`status-value ${isConnected ? 'status-good' : 'status-bad'}`}>
                  {overallStatus}
              </div>
           </div>
           {isConnected && ( // Only show quality if connected
               <div className="status-item">
                   <div className="status-label">Quality</div>
                   <div className={`status-value ${
                       connectionQuality === 'good' ? 'status-good' :
                       connectionQuality === 'degraded' ? 'status-degraded' : 'status-poor'
                   }`}>
                       {connectionQuality}
                   </div>
               </div>
           )}
           {/* Add other status items as needed (e.g., simulator status from context) */}
           {/*
           <div className="status-item">
               <div className="status-label">Simulator</div>
               <div className="status-value">{simulatorStatus}</div>
           </div>
           */}
        </div>
      </div>

      {/* Action Panel Example */}
      <div className="action-panel">
        <h2>Actions</h2>
        <div className="action-buttons">
            {/* Example action button - link or trigger function */}
            <button className="action-button" onClick={() => alert('Navigate to Trading...')}>
                {/* Add icon if desired */}
                <span>Trading Interface</span>
            </button>
            <button className="action-button" onClick={() => alert('Navigate to Simulator...')}>
                <span>Simulator Control</span>
            </button>
             <button className="action-button" onClick={() => alert('Navigate to Settings...')}>
                <span>Account Settings</span>
            </button>
        </div>
      </div>

      {/* Add more content specific to the home page */}

    </div>
  );
};

export default HomePage;
