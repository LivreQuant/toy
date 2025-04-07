import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ConnectionProvider } from './contexts/ConnectionContext';
import { ToastProvider } from './contexts/ToastContext';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import SimulatorPage from './pages/SimulatorPage';
import ProtectedRoute from './components/Common/ProtectedRoute'; // Component for protected routes

// --- Service Instantiation (Move to a bootstrapper file if complex) ---
import { TokenManager } from './services/auth/token-manager';
import { LocalStorageService } from './services/storage/local-storage-service';
import { HttpClient } from './api/http-client';
import { AuthApi } from './api/auth';
import { ConnectionManager } from './services/connection/connection-manager';
import { initializeLogging, getLogger } from './boot/logging'; // Import logging setup
import { AppErrorHandler } from './utils/app-error-handler';
import { toastService } from './services/notification/toast-service';
import { ErrorHandler } from './utils/error-handler'; // Import ErrorHandler
import { DeviceIdManager } from './utils/device-id-manager'; // Import DeviceIdManager

// Initialize Logging First
initializeLogging();
const logger = getLogger('App'); // Get logger instance

// Instantiate Core Services (Singleton or Scoped)
const storageService = new LocalStorageService();
const baseLogger = getLogger('ServiceCore'); // Use base logger for service instantiation
const errorHandler = new ErrorHandler(baseLogger.createChild('ErrorHandler'), toastService); // Use base logger

// Initialize Singletons that need setup
AppErrorHandler.initialize(baseLogger.createChild('AppErrorHandler'), toastService);
DeviceIdManager.getInstance(storageService, baseLogger.createChild('DeviceIdManager')); // Initialize DeviceIdManager

// Instantiate remaining services
const tokenManager = new TokenManager(storageService, errorHandler); // Pass errorHandler instance
const httpClient = new HttpClient(tokenManager); // HttpClient uses TokenManager
const authApi = new AuthApi(httpClient);
tokenManager.setAuthApi(authApi); // Important: Set AuthApi dependency in TokenManager

// Instantiate ConnectionManager (often a singleton or app-scoped)
const connectionManager = new ConnectionManager(tokenManager, {
  // Add any specific wsOptions or resilience options here if needed
});

logger.info('Application services instantiated.');
// --- End Service Instantiation ---


function App() {
  logger.info('Rendering App component');
  return (
    // Order matters: Toast > Auth > Connection
    <ToastProvider>
       <AuthProvider tokenManager={tokenManager} authApi={authApi}>
         <ConnectionProvider connectionManager={connectionManager}>
            <Router>
              <Routes>
                <Route path="/login" element={<LoginPage />} />

                {/* Protected Routes */}
                <Route path="/home" element={
                    <ProtectedRoute>
                       <HomePage />
                    </ProtectedRoute>
                } />
                 <Route path="/simulator" element={
                    <ProtectedRoute>
                       <SimulatorPage />
                    </ProtectedRoute>
                } />

                {/* Default route */}
                <Route path="/" element={<Navigate to="/home" replace />} />

                {/* Add other routes here */}
              </Routes>
            </Router>
         </ConnectionProvider>
       </AuthProvider>
    </ToastProvider>
  );
}

export default App;

