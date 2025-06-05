// src/components/Layout/AuthenticatedLayout.tsx
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