// App.tsx 
import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';

// LOGGING
import { initializeLogging } from './boot/logging'; // Import logging setup

// SERVICES
import { LocalStorageService } from './services/storage/local-storage-service';
import { SessionStorageService } from './services/storage/session-storage-service';
import { DeviceIdManager } from './services/auth/device-id-manager';
import { TokenManager } from './services/auth/token-manager';

// APIS
import { HttpClient } from './api/http-client';
import { AuthApi } from './api/auth';
import { OrdersApi } from './api/order';

// SERVICES
import { ConnectionManager } from './services/connection/connection-manager';
import { OrderService } from './services/orders/order-service';

// HOOKS
import { useConnection } from './hooks/useConnection';

// CONTEXT
import { ToastProvider } from './contexts/ToastContext';
import { AuthProvider } from './contexts/AuthContext';
import { TokenManagerProvider } from './contexts/TokenManagerContext';
import { ConnectionProvider } from './contexts/ConnectionContext';

// COMPONENTS
import ProtectedRoute from './components/Common/ProtectedRoute'; // Component for protected routes

// PAGES
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import SimulatorPage from './pages/SimulatorPage';
import SessionDeactivatedPage from './pages/SessionDeactivatedPage';

// Initialize Logging First
initializeLogging()

// --- Start Service Instantiation ---

// Instantiate Storage
const localStorageService = new LocalStorageService();
const sessionStorageService = new SessionStorageService();

DeviceIdManager.getInstance(sessionStorageService);
const tokenManager = new TokenManager(
  localStorageService, 
  DeviceIdManager.getInstance(sessionStorageService)
);

// Intialize Rest APIs + Websocket
const httpClient = new HttpClient(tokenManager);
const authApi = new AuthApi(httpClient);
const ordersApi = new OrdersApi(httpClient);

tokenManager.setAuthApi(authApi);

const connectionManager = new ConnectionManager(
  tokenManager,
  httpClient
);

const orderService = new OrderService(
  ordersApi, 
  tokenManager
);

// --- End Service Instantiation ---

function DeviceIdInvalidationHandler({ children }: { children: React.ReactNode }) {
  // websocket message "device_id_invalidated" routes user to session-deactivated Page
  const navigate = useNavigate();
  const { connectionManager } = useConnection();
  
  useEffect(() => {
    if (!connectionManager) return;
    
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
  return (
    // Order matters: Toast > Auth > Connection
    <ToastProvider>
       <AuthProvider tokenManager={tokenManager} authApi={authApi} connectionManager={connectionManager}>
        <TokenManagerProvider tokenManager={tokenManager}>
          <ConnectionProvider connectionManager={connectionManager}>
              <Router>
                <DeviceIdInvalidationHandler>
                  <Routes>
                    {/* Simulator page */}
                    <Route path="/login" element={
                      <LoginPage />
                    } />

                    {/* Session page */}
                    <Route path="/home" element={
                        <ProtectedRoute>
                          <HomePage />
                        </ProtectedRoute>
                    } />

                    {/* Simulator page */}
                    <Route path="/simulator" element={
                        <ProtectedRoute>
                          <SimulatorPage />
                        </ProtectedRoute>
                    } />

                    {/* Deactivate session */}
                    <Route path="/session-deactivated" element={
                      <SessionDeactivatedPage />
                    } />

                    {/* Default route - Unprotected 404 Page*/}
                    <Route path="/" element={
                      <Navigate to="/home" replace />
                    } />

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