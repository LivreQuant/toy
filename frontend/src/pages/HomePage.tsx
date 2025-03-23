import React from 'react';
import { Link } from 'react-router-dom';
import { useConnection } from '../contexts/ConnectionContext';
import { useAuth } from '../contexts/AuthContext';

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
            <div className="status-label">Session ID</div>
            <div className="status-value">
              {connectionState.sessionId || 'None'}
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

      <style jsx>{`
        .home-page {
          padding: 20px;
          max-width: 1200px;
          margin: 0 auto;
        }
        
        .home-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }
        
        .logout-button {
          padding: 8px 16px;
          background-color: #f44336;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
        }
        
        .status-panel, .action-panel {
          background-color: white;
          border-radius: 8px;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
          padding: 20px;
          margin-bottom: 20px;
        }
        
        .status-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          gap: 15px;
        }
        
        .status-item {
          border: 1px solid #eee;
          padding: 10px;
          border-radius: 6px;
        }
        
        .status-label {
          font-size: 0.9rem;
          color: #666;
          margin-bottom: 5px;
        }
        
        .status-value {
          font-weight: bold;
          font-size: 1.1rem;
        }
        
        .status-good {
          color: #2ecc71;
        }
        
        .status-bad {
          color: #e74c3c;
        }
        
        .status-degraded {
          color: #f39c12;
        }
        
        .status-poor {
          color: #e74c3c;
        }
        
        .action-buttons {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          gap: 15px;
        }
        
        .action-button {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 20px;
          background-color: #f9f9f9;
          border: 1px solid #ddd;
          border-radius: 8px;
          text-decoration: none;
          color: #333;
          transition: all 0.2s ease;
          cursor: pointer;
        }
        
        .action-button:hover:not([disabled]) {
          background-color: #f2f2f2;
          transform: translateY(-2px);
          box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }
        
        .action-button[disabled] {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        .action-icon {
          font-size: 24px;
          margin-bottom: 10px;
        }
      `}</style>
    </div>
  );
};

export default HomePage;