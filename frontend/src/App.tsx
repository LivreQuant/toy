// src/App.tsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { SessionProvider } from './contexts/SessionContext';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import SimulatorPage from './pages/SimulatorPage';
import ConnectionStatus from './components/Common/ConnectionStatus';

const App: React.FC = () => {
  return (
    <AuthProvider>
      <SessionProvider>
        <MarketDataProvider>
          <Router>
            <div className="app-container">
              <div className="app-header">
                <ConnectionStatus />
              </div>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/home" element={<RequireAuth><HomePage /></RequireAuth>} />
                <Route path="/simulator" element={<RequireAuth><SimulatorPage /></RequireAuth>} />
                <Route path="/" element={<Navigate to="/home" replace />} />
              </Routes>
            </div>
          </Router>
        </MarketDataProvider>
      </SessionProvider>
    </AuthProvider>
  );
};

// Require authentication wrapper
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) {
    return <div className="loading-container">Loading...</div>;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
};

export default App;