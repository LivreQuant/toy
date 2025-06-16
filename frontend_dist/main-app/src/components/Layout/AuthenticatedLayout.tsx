// src/components/Layout/AuthenticatedLayout.tsx
/*
import React from 'react';
import { useConnection } from '../../hooks/useConnection';
import ConnectionStatusBar from '../Common/ConnectionStatusBar';
import './AuthenticatedLayout.css';

interface AuthenticatedLayoutProps {
  children: React.ReactNode;
}

const AuthenticatedLayout: React.FC<AuthenticatedLayoutProps> = ({ children }) => {
  // Use useConnection to get the same state as ConnectionStatusIndicator
  const { connectionState, connectionManager } = useConnection();

  const handleManualReconnect = () => {
    if (connectionManager) {
      connectionManager.manualReconnect();
    }
  };

  return (
    <div className="authenticated-layout">
      <div className="content">
        {children}
      </div>
      {connectionState && (
        <ConnectionStatusBar 
          state={connectionState} 
          onManualReconnect={handleManualReconnect} 
        />
      )}
    </div>
  );
};

export default AuthenticatedLayout;
*/

// Alternative version with simple online status
import React from 'react';
import './AuthenticatedLayout.css';

interface AuthenticatedLayoutProps {
  children: React.ReactNode;
}

const AuthenticatedLayout: React.FC<AuthenticatedLayoutProps> = ({ children }) => {
  return (
    <div className="authenticated-layout">
      <div className="content">
        {children}
      </div>
      {/* Simple status for main app */}
      <div className="main-app-status">
        <span style={{ color: 'green', fontSize: '12px' }}>
          📡 Main App Online
        </span>
      </div>
    </div>
  );
};

export default AuthenticatedLayout;