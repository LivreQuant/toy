import React from 'react';
import { Link } from 'react-router-dom';
import { useConnection } from '../contexts/ConnectionContext';
import { useAuth } from '../contexts/AuthContext';
import './HomePage.css';

const HomePage: React.FC = () => {
  const { isConnected, connectionState } = useConnection();
  const { logout } = useAuth();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className="home-page">
      <div className="home-header">
        <h1>Trading Simulator Dashboard</h1>
        <button onClick={handleLogout} className="logout-button">Logout</button>
      </div>

      <div className="status-panel">
        <h2>System Status</h2>
        <div className="status-grid">
          <div className="status-item">
            <div className="status-label">Connection</div>
            <div className={`status-value ${isConnected ? 'status-good' : 'status-bad'}`}>
              {isConnected ? 'Connected' : 'Disconnected'}
            </div>
          </div>
          <div className="status-item">
            <div className="status-label">Simulator</div>
            <div className="status-value">
              {connectionState.simulatorStatus || 'Unknown'}
            </div>
          </div>
          <div className="status-item">
            <div className="status-label">Connection Quality</div>
            <div className={`status-value status-${connectionState.connectionQuality}`}>
              {connectionState.connectionQuality}
            </div>
          </div>
        </div>
      </div>

      <div className="action-panel">
        <h2>Quick Actions</h2>
        <div className="action-buttons">
          <Link to="/simulator" className="action-button">
            <span className="action-icon">📈</span>
            <span className="action-text">Open Simulator</span>
          </Link>
          <button className="action-button" disabled={!isConnected}>
            <span className="action-icon">📝</span>
            <span className="action-text">View Orders</span>
          </button>
          <button className="action-button" disabled={!isConnected}>
            <span className="action-icon">💼</span>
            <span className="action-text">Portfolio</span>
          </button>
          <button className="action-button">
            <span className="action-icon">⚙️</span>
            <span className="action-text">Settings</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default HomePage;