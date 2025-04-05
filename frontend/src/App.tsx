// src/App.tsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ConnectionProvider, useConnection } from './contexts/ConnectionContext';
import { ToastProvider } from './contexts/ToastContext';
import { toastService } from './services/notification/toast-service'; // Singleton toast service

// --- Import Services and APIs ---
import { TokenManager } from './services/auth/token-manager';
import { LocalStorageService } from './services/storage/local-storage-service';
import { ErrorHandler } from './utils/error-handler';
import { Logger } from './utils/logger';
import { HttpClient } from './api/http-client';
import { AuthApi } from './api/auth';
// Ensure DeviceIdManager is initialized if needed (adjust path if necessary)
import { DeviceIdManager } from './utils/device-id-manager';

// Import components
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import SimulatorPage from './pages/SimulatorPage';
// Assuming you have a component named ConnectionStatusDisplay or similar
import ConnectionStatus from './components/Common/ConnectionStatus'; // Use your actual component
import ErrorBoundary from './components/Common/ErrorBoundary';
import LoadingScreen from './components/Common/LoadingScreen';
import ConnectionRecoveryDialog from './components/Common/ConnectionRecoveryDialog';
import ConnectionStatusOverlay from './components/Common/ConnectionStatusOverlay';

// Hooks
import { useAuth } from './contexts/AuthContext';
import { useToast } from './contexts/ToastContext';


// --- Instantiate Services ---
// These are created once when the application loads
const logger = Logger.getInstance();
const storageService = new LocalStorageService();
// Initialize DeviceIdManager (needs to be done once, typically at app startup)
DeviceIdManager.getInstance(storageService, logger);
const errorHandler = new ErrorHandler(logger, toastService);

// Instantiate TokenManager (pass StorageService, ErrorHandler)
const tokenManager = new TokenManager(storageService, errorHandler);

// Instantiate HttpClient (pass TokenManager)
const httpClient = new HttpClient(tokenManager);

// Instantiate AuthApi (pass HttpClient)
const authApi = new AuthApi(httpClient);

// --- Link AuthApi back to TokenManager ---
// This resolves the circular dependency after all instances are created
tokenManager.setAuthApi(authApi);
// Now tokenManager is fully configured and ready to be used


const App: React.FC = () => {
  // Services (logger, tokenManager, authApi) are instantiated above

  return (
    // Pass logger to ErrorBoundary if it accepts it as a prop
    <ErrorBoundary logger={logger}>
      <ToastProvider>
        {/* Pass instantiated services to AuthProvider */}
        <AuthProvider tokenManager={tokenManager} authApi={authApi}>
          {/* Pass instantiated services to ConnectionProvider */}
          <ConnectionProvider tokenManager={tokenManager} logger={logger}>
            {/* AppContent consumes the contexts */}
            <AppContent />
          </ConnectionProvider>
        </AuthProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
};

// AppContent component remains largely the same, consuming contexts
const AppContent: React.FC = () => {
  const { addToast } = useToast(); // From ToastContext
  // isLoading likely comes from AuthContext to check initial auth status
  const { isLoading } = useAuth();

  // Connect the singleton toastService to the actual addToast function from context
  React.useEffect(() => {
    toastService.setToastMethod(addToast);
    // Cleanup function if needed when AppContent unmounts
    // return () => { toastService.setToastMethod(null); };
  }, [addToast]);

  // Show loading screen during initial auth check
  if (isLoading) {
    return <LoadingScreen message="Initializing..." />;
  }

  return (
    <Router>
      <div className="app-container">
        <header className="app-header">
          {/* ConnectionStatusWrapper consumes ConnectionContext */}
          <ConnectionStatusWrapper />
        </header>
        <main className="app-main-content"> {/* Added a main wrapper */}
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              {/* Protected Routes */}
              <Route path="/home" element={<RequireAuth><HomePage /></RequireAuth>} />
              <Route path="/simulator" element={<RequireAuth><SimulatorPage /></RequireAuth>} />
              {/* Default route */}
              <Route path="/" element={<Navigate to="/home" replace />} />
              {/* Optional: Add a 404 Not Found route */}
              {/* <Route path="*" element={<NotFoundPage />} /> */}
            </Routes>
        </main>
        {/* Overlays consuming ConnectionContext */}
        <ConnectionStatusOverlay />
        <ConnectionRecoveryDialog />
      </div>
    </Router>
  );
};

// Wrapper to display connection status, consuming ConnectionContext
const ConnectionStatusWrapper: React.FC = () => {
  const { isAuthenticated } = useAuth(); // Check if user is logged in
  const {
    overallStatus,
    connectionQuality,
    isRecovering,
    recoveryAttempt,
    manualReconnect, // Function to trigger manual reconnect
    simulatorStatus // Assuming ConnectionContext provides this
  } = useConnection();

  // Don't show connection status if user is not authenticated
  if (!isAuthenticated) {
    return null;
  }

  // Use your actual ConnectionStatus component and pass props from context
  return (
    <ConnectionStatus
      status={overallStatus}
      quality={connectionQuality}
      isRecovering={isRecovering}
      recoveryAttempt={recoveryAttempt}
      onManualReconnect={manualReconnect}
      simulatorStatus={simulatorStatus} // Pass simulator status if available
    />
  );
};


// Wrapper component to protect routes requiring authentication
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth(); // Get auth state and loading status

  // Show loading screen while checking authentication
  if (isLoading) {
    return <LoadingScreen message="Verifying authentication..." />;
  }

  // If not authenticated, redirect to login page
  if (!isAuthenticated) {
    // You could optionally pass the intended destination via state
    // import { useLocation } from 'react-router-dom';
    // const location = useLocation();
    // return <Navigate to="/login" state={{ from: location }} replace />;
    return <Navigate to="/login" replace />;
  }

  // If authenticated, render the child components (the protected page)
  return <>{children}</>;
};

export default App;