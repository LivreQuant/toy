// src/App.tsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ConnectionProvider } from './contexts/ConnectionContext';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import SimulatorPage from './pages/SimulatorPage';
import ConnectionStatus from './components/Common/ConnectionStatus';
import ErrorBoundary from './components/Common/ErrorBoundary';
import LoadingScreen from './components/Common/LoadingScreen';
import { useAuth } from './contexts/AuthContext';
import { useConnection } from './contexts/ConnectionContext';
import ConnectionRecoveryDialog from './components/Common/ConnectionRecoveryDialog';

const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <ConnectionProvider>
          <AppRouter />
          <ConnectionRecoveryDialog />
        </ConnectionProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
};

const AppRouter: React.FC = () => {
  const { isLoading } = useAuth();
  
  if (isLoading) {
    return <LoadingScreen message="Loading application..." />;
  }
  
  return (
    <Router>
      <div className="app-container">
        <div className="app-header">
          <ConnectionStatusWrapper />
        </div>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/home" element={<RequireAuth><HomePage /></RequireAuth>} />
          <Route path="/simulator" element={<RequireAuth><SimulatorPage /></RequireAuth>} />
          <Route path="/" element={<Navigate to="/home" replace />} />
        </Routes>
      </div>
    </Router>
  );
};

// Connection status with current state
const ConnectionStatusWrapper: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const { isConnected, isConnecting, connectionQuality, connectionState } = useConnection();
  // Only show connection status if authenticated
  if (!isAuthenticated) {
    return null;
  }
  
  return (
    <ConnectionStatus 
      isConnected={isConnected}
      isConnecting={isConnecting}
      connectionQuality={connectionQuality}
      simulatorStatus={connectionState.simulatorStatus}
    />
  );
};

// Require authentication wrapper - simplified to not trigger connections
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) {
    return <LoadingScreen message="Checking authentication..." />;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Simply return children - connection is managed by ConnectionContext
  return <>{children}</>;
};

export default App;