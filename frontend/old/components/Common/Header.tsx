// src/components/Common/Header.tsx
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import Logout from '../Auth/Logout';
import ConnectionIndicator from '../Connection/ConnectionIndicator';
import { useConnection } from '../../contexts/ConnectionContext';
import './Header.css';

const Header: React.FC = () => {
  const location = useLocation();
  const { isConnected, simulatorStatus } = useConnection();
  
  // Don't show header on login page
  if (location.pathname === '/login') {
    return null;
  }
  
  return (
    <header className="app-header">
      <div className="logo">
        <Link to="/home">
          <h1>Trading Simulator</h1>
        </Link>
      </div>
      
      <nav className="main-nav">
        <ul>
          <li className={location.pathname === '/home' ? 'active' : ''}>
            <Link to="/home">Home</Link>
          </li>
          {isConnected && simulatorStatus === 'RUNNING' && (
            <li className={location.pathname === '/simulator' ? 'active' : ''}>
              <Link to="/simulator">Simulator</Link>
            </li>
          )}
        </ul>
      </nav>
      
      <div className="header-controls">
        <ConnectionIndicator />
        <Logout />
      </div>
    </header>
  );
};

export default Header;