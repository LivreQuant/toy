// src/App.tsx
import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';

// LOGGING
import { initializeLogging } from './boot/logging'; // Import logging setup

// SERVICES
import { LocalStorageService } from '@shared/services';
import { SessionStorageService } from '@shared/services';
import { DeviceIdManager } from './services/auth/device-id-manager';
import { TokenManager } from './services/auth/token-manager';

// APIS
import { HttpClient } from './api/http-client';
import { AuthApi } from './api/auth';
import { ConvictionsApi } from './api/conviction';

// SERVICES
import { ConnectionManager } from './services/connection/connection-manager';
import { ConvictionManager } from './services/convictions/conviction-manager';

// HOOKS
import { useConnection } from './hooks/useConnection';

// CONTEXT
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';
import { AuthProvider } from './contexts/AuthContext';
import { TokenManagerProvider } from './contexts/TokenManagerContext';
import { ConnectionProvider } from './contexts/ConnectionContext';
import { ConvictionProvider } from './contexts/ConvictionContext';
import { BookManagerProvider } from './contexts/BookContext';
import { FundProvider } from './contexts/FundContext';

// COMPONENTS
import ProtectedRoute from './components/Common/ProtectedRoute'; // Component for protected routes

// LAYOUT 
import AuthenticatedLayout from './components/Layout/AuthenticatedLayout';

// PAGES
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/Auth/LoginPage';
import SignupPage from './pages/Auth/SignupPage';
import VerifyEmailPage from './pages/Auth/VerifyEmailPage';
import ForgotUsernamePage from './pages/Auth/ForgotUsernamePage';
import ForgotPasswordPage from './pages/Auth/ForgotPasswordPage';
import ResetPasswordPage from './pages/Auth/ResetPasswordPage';
import HomePage from './pages/HomePage';
import SimulatorPage from './pages/SimulatorPage';
import BookDetailsPage from './pages/BookDetailsPage';
import SessionDeactivatedPage from './pages/SessionDeactivatedPage';
import EnterpriseContactPage from './pages/EnterpriseContactPage';

import FundProfileForm from './components/Profile/FundProfileForm';
import EditFundProfileForm from './components/Profile/EditFundProfileForm';

import BookSetupPage from './components/Book/BookSetupPage';
import EditBookPage from './components/Book/EditBookPage';

// Initialize Logging First
initializeLogging();

// --- Start Service Instantiation ---

// Instantiate Storage
const localStorageService = new LocalStorageService();
const sessionStorageService = new SessionStorageService();

DeviceIdManager.getInstance(sessionStorageService);
const tokenManager = new TokenManager(
  localStorageService, 
  DeviceIdManager.getInstance(sessionStorageService)
);

// Initialize Rest APIs + Websocket
const httpClient = new HttpClient(tokenManager);
const authApi = new AuthApi(httpClient);
const convictionsApi = new ConvictionsApi(httpClient);

tokenManager.setAuthApi(authApi);

const connectionManager = new ConnectionManager(
  tokenManager
);

const convictionManager = new ConvictionManager(
  convictionsApi, 
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

// Separate routes component for better organization
const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/forgot-username" element={<ForgotUsernamePage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/enterprise-contact" element={<EnterpriseContactPage />} />
      
      {/* Session page */}
      <Route path="/home" element={
        <ProtectedRoute>
          <AuthenticatedLayout>
            <HomePage />
          </AuthenticatedLayout>
        </ProtectedRoute>
      } />

      <Route path="/profile/create" element={
        <ProtectedRoute>
          <AuthenticatedLayout>
            <FundProfileForm />
          </AuthenticatedLayout>
        </ProtectedRoute>
      } />

      {/* Add this new route */}
      <Route path="/profile/edit" element={
        <ProtectedRoute>
          <AuthenticatedLayout>
            <EditFundProfileForm />
          </AuthenticatedLayout>
        </ProtectedRoute>
      } />

      {/* Book initialize */}
      <Route path="/books/new" element={
        <ProtectedRoute>
          <AuthenticatedLayout>
            <BookSetupPage />
          </AuthenticatedLayout>
        </ProtectedRoute>
      } />

      {/* Book edit route */}
      <Route path="/books/:bookId/edit" element={
        <ProtectedRoute>
          <AuthenticatedLayout>
            <EditBookPage />
          </AuthenticatedLayout>
        </ProtectedRoute>
      } />
      
      <Route path="/books/:bookId" element={
        <ProtectedRoute>
          <AuthenticatedLayout>
            <BookDetailsPage />
          </AuthenticatedLayout>
        </ProtectedRoute>
      } />

      {/* Simulator page */}
      <Route path="/simulator/:simulationId" element={
        <ProtectedRoute>
          <AuthenticatedLayout>
            <SimulatorPage />
          </AuthenticatedLayout>
        </ProtectedRoute>
      } />

      {/* Deactivate session */}
      <Route path="/session-deactivated" element={
          <AuthenticatedLayout>
            <SessionDeactivatedPage />
          </AuthenticatedLayout>
      } />

      {/* Default route - Redirect to home */}
      <Route path="*" element={
        <Navigate to="/home" replace />
      } />
    </Routes>
  );
};

function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider tokenManager={tokenManager} authApi={authApi} connectionManager={connectionManager}>
          <TokenManagerProvider tokenManager={tokenManager}>
            <BookManagerProvider>
              <ConvictionProvider convictionManager={convictionManager}>
                <ConnectionProvider connectionManager={connectionManager}>
                  <FundProvider>  
                    <Router>
                      <DeviceIdInvalidationHandler>
                        <AppRoutes />
                      </DeviceIdInvalidationHandler>
                    </Router>
                  </FundProvider>
                </ConnectionProvider>
              </ConvictionProvider>
            </BookManagerProvider>
          </TokenManagerProvider>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default App;