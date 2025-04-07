// src/pages/HomePage.tsx
import React from 'react';
import { useConnectionState, useConnectionActions } from '../contexts/ConnectionContext';
import { useAuthState } from '../hooks/useAppState';
import { useAuth } from '../contexts/AuthContext';
import './HomePage.css';

const HomePage: React.FC = () => {
  // Use reactive state hooks for state
  const connectionState = useConnectionState();
  const authState = useAuthState();
  
  // Use context hooks for actions
  const { logout } = useAuth();
  
  // Event Handler for Logout
  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error("Logout failed:", error);
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
              <div className={`status-value ${connectionState.status === 'CONNECTED' ? 'status-good' : 'status-bad'}`}>
                  {connectionState.status}
              </div>
           </div>
           {connectionState.status === 'CONNECTED' && (
               <div className="status-item">
                   <div className="status-label">Quality</div>
                   <div className={`status-value ${
                       connectionState.quality === 'good' ? 'status-good' :
                       connectionState.quality === 'degraded' ? 'status-degraded' : 'status-poor'
                   }`}>
                       {connectionState.quality}
                   </div>
               </div>
           )}
           <div className="status-item">
               <div className="status-label">Simulator</div>
               <div className="status-value">{connectionState.simulatorStatus}</div>
           </div>
           <div className="status-item">
               <div className="status-label">User ID</div>
               <div className="status-value">{authState.userId || 'N/A'}</div>
           </div>
        </div>
      </div>

      {/* Action Panel Example */}
      <div className="action-panel">
        <h2>Actions</h2>
        <div className="action-buttons">
            <button className="action-button" onClick={() => alert('Navigate to Trading...')}>
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
    </div>
  );
};

export default HomePage;