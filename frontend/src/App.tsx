// src/App.tsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConnectionProvider, useConnection } from './contexts/ConnectionContext';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import SimulatorPage from './pages/SimulatorPage';
import ReconnectionStatus from './components/ReconnectionStatus';
import GlobalErrorBoundary from './components/GlobalErrorBoundary';

const App: React.FC = () => {
  return (
    <GlobalErrorBoundary>
      <ConnectionProvider>
        <Router>
          <ReconnectionStatus />
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/home" element={<RequireAuth><HomePage /></RequireAuth>} />
            <Route path="/simulator" element={<RequireAuth><SimulatorPage /></RequireAuth>} />
            <Route path="/" element={<Navigate to="/home" replace />} />
          </Routes>
        </Router>
      </ConnectionProvider>
    </GlobalErrorBoundary>
  );
};

// Require authentication wrapper
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { hasSession, isConnecting, tokenManager } = useConnection();
  
  // Check for valid authentication first
  if (!tokenManager.isAuthenticated()) {
    // Not authenticated, redirect to login
    return <Navigate to="/login" replace />;
  }
  
  // If connected to a session, allow access
  if (hasSession) {
    return <>{children}</>;
  }
  
  // If connecting, show loading
  if (isConnecting) {
    return <div className="loading-container">Connecting to session...</div>;
  }
  
  // Not connected and not connecting, redirect to login
  return <Navigate to="/login" replace />;
};

export default App;