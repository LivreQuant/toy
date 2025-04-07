// src/App.tsx
import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ConnectionProvider } from './contexts/ConnectionContext';
import { ToastProvider } from './contexts/ToastContext';
import { getLogger } from './boot/logging';
import { AppErrorHandler } from './utils/app-error-handler';
import { toastService } from './services/notification/toast-service';

// Import components
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import SimulatorPage from './pages/SimulatorPage';
import ConnectionStatus from './components/Common/ConnectionStatus';
import ErrorBoundary from './components/Common/ErrorBoundary';
import LoadingScreen from './components/Common/LoadingScreen';
import ConnectionRecoveryDialog from './components/Common/ConnectionRecoveryDialog';
import ConnectionStatusOverlay from './components/Common/ConnectionStatusOverlay';

// Import services
import { TokenManager } from './services/auth/token-manager';
import { LocalStorageService } from './services/storage/local-storage-service';
import { DeviceIdManager } from './utils/device-id-manager';
import { HttpClient } from './api/http-client';
import { AuthApi } from './api/auth';

// Import hooks
import { useAuth } from './contexts/AuthContext';
import { useToast } from './contexts/ToastContext';

// Conditionally import DevTools page in development
const DevToolsPage = process.env.NODE_ENV === 'development' 
  ? React.lazy(() => import('./pages/DevToolsPage'))
  : null;

// Get logger for App
const logger = getLogger('App');

// --- Instantiate Services ---
const storageService = new LocalStorageService();

// Initialize DeviceIdManager
DeviceIdManager.getInstance(storageService, logger);

// Initialize the global error handler
AppErrorHandler.initialize(logger, toastService);

// Instantiate TokenManager
const tokenManager = new TokenManager(storageService, AppErrorHandler.getInstance());

// Instantiate HttpClient
const httpClient = new HttpClient(tokenManager);

// Instantiate AuthApi
const authApi = new AuthApi(httpClient);

// Link AuthApi back to TokenManager
tokenManager.setAuthApi(authApi);

const App: React.FC = () => {
  useEffect(() => {
    logger.info('Application initialized');
  }, []);

  return (
    <ErrorBoundary logger={logger}>
      <ToastProvider>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
};

const AppContent: React.FC = () => {
  const { addToast } = useToast();
  const { isLoading, isAuthenticated } = useAuth();

  // Connect the singleton toastService to the actual addToast function from context
  React.useEffect(() => {
    toastService.setToastMethod(addToast);
    return () => { toastService.setToastMethod(null); };
  }, [addToast]);

  // Show loading screen during initial auth check
  if (isLoading) {
    return <LoadingScreen message="Initializing..." />;
  }

  return (
    <Router>
      <div className="app-container">
        {isAuthenticated ? (
          <>
            <ConnectionProvider tokenManager={tokenManager} logger={logger}>
              <header className="app-header">
                <ConnectionStatus />
              </header>
              <main className="app-main-content">
                <Routes>
                  <Route path="/home" element={<HomePage />} />
                  <Route path="/simulator" element={<SimulatorPage />} />
                  {DevToolsPage && (
                    <Route path="/dev-tools" element={
                      <React.Suspense fallback={<LoadingScreen message="Loading Dev Tools..." />}>
                        <DevToolsPage />
                      </React.Suspense>
                    } />
                  )}
                  <Route path="/" element={<Navigate to="/home" replace />} />
                </Routes>
              </main>
              <ConnectionStatusOverlay />
              <ConnectionRecoveryDialog />
            </ConnectionProvider>
          </>
        ) : (
          <main className="app-main-content">
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="*" element={<Navigate to="/login" replace />} />
            </Routes>
          </main>
        )}
      </div>
    </Router>
  );
};

export default App;