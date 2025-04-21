// App.tsx 
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ConnectionProvider } from './contexts/ConnectionContext';
import { TokenManagerProvider } from './contexts/TokenManagerContext';
import { ToastProvider } from './contexts/ToastContext';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import SimulatorPage from './pages/SimulatorPage';
import SessionDeactivatedPage from './pages/SessionDeactivatedPage';
import ProtectedRoute from './components/Common/ProtectedRoute'; // Component for protected routes

// --- Service Instantiation (Move to a bootstrapper file if complex) ---
import { TokenManager } from './services/auth/token-manager';
import { LocalStorageService } from './services/storage/local-storage-service';
import { SessionStorageService } from './services/storage/session-storage-service';
import { HttpClient } from './api/http-client';
import { AuthApi } from './api/auth';
import { WebSocketManager } from './services/websocket/websocket-manager';
import { OrdersApi } from './api/order';
import { SessionApi } from './api/session';
import { SimulatorApi } from './api/simulator';
import { ConnectionManager } from './services/connection/connection-manager';
import { initializeLogging, getLogger } from './boot/logging'; // Import logging setup
import { AppErrorHandler } from './utils/app-error-handler';
import { toastService } from './services/notification/toast-service';
import { ErrorHandler } from './utils/error-handler'; // Import ErrorHandler
import { DeviceIdManager } from './services/auth/device-id-manager'; // Import DeviceIdManager

import { useNavigate } from 'react-router-dom';
import { useConnection } from './hooks/useConnection';
import { useEffect } from 'react';

// Initialize Logging First
initializeLogging();
const logger = getLogger('App'); // Get logger instance

// Instantiate Core Services (Singleton or Scoped)
const localStorageService = new LocalStorageService();
const sessionStorageService = new SessionStorageService();
const baseLogger = getLogger('ServiceCore'); // Use base logger for service instantiation
const errorHandler = new ErrorHandler(baseLogger.createChild('ErrorHandler'), toastService); // Use base logger

// Initialize Singletons that need setup
AppErrorHandler.initialize(baseLogger.createChild('AppErrorHandler'), toastService);
DeviceIdManager.getInstance(sessionStorageService, baseLogger.createChild('DeviceIdManager')); // Initialize DeviceIdManager

// Instantiate remaining services
const tokenManager = new TokenManager(localStorageService, errorHandler, DeviceIdManager.getInstance(sessionStorageService, logger)); // Pass errorHandler instance
const httpClient = new HttpClient(tokenManager); // HttpClient uses TokenManager
const authApi = new AuthApi(httpClient);
tokenManager.setAuthApi(authApi); // Important: Set AuthApi dependency in TokenManager

// Instantiate WebSocketManager for session/simulator
const wsManager = new WebSocketManager(tokenManager, {
  // Add any specific wsOptions here if needed
  preventAutoConnect: true // This is important for connection control
});

// Keep OrdersApi using HTTP
const ordersApi = new OrdersApi(httpClient);

// Now instantiate the updated APIs that use WebSocket
const sessionApi = new SessionApi(wsManager);
const simulatorApi = new SimulatorApi(wsManager);

// Instantiate ConnectionManager with both WebSocketManager and HttpClient
const connectionManager = new ConnectionManager(tokenManager, {
  // Use the wsManager we created
  wsManager: wsManager,
  // Add any specific resilience options here if needed
});

logger.info('Application services instantiated.');
// --- End Service Instantiation ---

function DeviceIdInvalidationHandler({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const { connectionManager } = useConnection(); // Destructure to get connectionManager
  
  
  useEffect(() => {
    if (!connectionManager) return;
    
    console.log("Setting up device_id_invalidated listener");
    
    // Subscribe to device_id_invalidated events
    const subscription = connectionManager.on('device_id_invalidated').subscribe((eventData) => {
      console.error("🚨 DEVICE ID INVALIDATED - REDIRECTING TO SESSION DEACTIVATED PAGE", {
        eventData,
        currentPath: window.location.pathname,
        timestamp: new Date().toISOString()
      });
      
      // Force immediate redirect to session deactivated page
      navigate('/session-deactivated', { replace: true });
    });
    
    return () => {
      subscription.unsubscribe();
    };
  }, [connectionManager, navigate]);
  
  return <>{children}</>;
}

function App() {
  logger.info('Rendering App component');
  return (
    // Order matters: Toast > Auth > Connection
    <ToastProvider>
       <AuthProvider tokenManager={tokenManager} authApi={authApi} connectionManager={connectionManager}>
        <TokenManagerProvider tokenManager={tokenManager}>
          <ConnectionProvider connectionManager={connectionManager}>
              <Router>
                <DeviceIdInvalidationHandler>
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

                    <Route path="/session-deactivated" element={<SessionDeactivatedPage />} />

                    {/* Default route */}
                    <Route path="/" element={<Navigate to="/home" replace />} />

                    {/* Add other routes here */}
                  </Routes>
                </DeviceIdInvalidationHandler>
              </Router>
          </ConnectionProvider>
         </TokenManagerProvider>
       </AuthProvider>
    </ToastProvider>
  );
}

export default App;