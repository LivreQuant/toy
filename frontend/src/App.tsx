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
import { OrdersApi } from './api/order';
import { SessionApi } from './api/session';
import { SimulatorApi } from './api/simulator';
import { ConnectionManager } from './services/connection/connection-manager';
import { initializeLogging, getLogger } from './boot/logging'; // Import logging setup
import { toastService } from './services/notification/toast-service';
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

// Initialize Singletons that need setup
DeviceIdManager.getInstance(sessionStorageService, baseLogger.createChild('DeviceIdManager')); // Initialize DeviceIdManager

// Instantiate remaining services
const tokenManager = new TokenManager(
  localStorageService, 
  DeviceIdManager.getInstance(sessionStorageService, logger)
);
const httpClient = new HttpClient(tokenManager); // HttpClient uses TokenManager
const authApi = new AuthApi(httpClient);
tokenManager.setAuthApi(authApi); // Important: Set AuthApi dependency in TokenManager

// Keep OrdersApi using HTTP
const ordersApi = new OrdersApi(httpClient);

// Instantiate ConnectionManager with both WebSocketManager and HttpClient
const connectionManager = new ConnectionManager(
  tokenManager,
  httpClient
);

logger.info('Application services instantiated.');
// --- End Service Instantiation ---

function DeviceIdInvalidationHandler({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const { connectionManager } = useConnection();
  
  useEffect(() => {
    if (!connectionManager) return;
    
    console.log("Setting up device_id_invalidated listener");
    
    // Use the new event subscription method
    const subscription = connectionManager.on('device_id_invalidated', (data) => {
      console.error("🚨 DEVICE ID INVALIDATED - REDIRECTING TO SESSION DEACTIVATED PAGE", {
        data,
        currentPath: window.location.pathname,
        timestamp: new Date().toISOString()
      });
      
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