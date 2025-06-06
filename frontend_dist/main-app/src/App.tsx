// frontend_dist/main-app/src/App.tsx
import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';

// LOGGING - now from package
import { initializeLogging, getLogger } from '@trading-app/logging';

// AUTH SERVICES - now from auth package
import { AuthFactory, DeviceIdManager, TokenManager } from '@trading-app/auth';

// WEBSOCKET SERVICES - now from websocket package
import { 
  ConnectionManager, 
  createConnectionManagerWithGlobalDeps 
} from '@trading-app/websocket';

// APIS - keep existing structure
import { HttpClient } from './api/http-client';
import { AuthApi } from './api/auth';
import { ConvictionsApi } from './api/conviction';

// SERVICES - keep existing services that aren't websocket related
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
import ProtectedRoute from './components/Common/ProtectedRoute';

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

// Create a logger for App.tsx debugging
const logger = getLogger('App');

// --- Start Service Instantiation ---

logger.info('🚀 Starting service instantiation...');

// Log environment information for debugging
logger.info('🔍 APP STARTUP: Environment information', {
  NODE_ENV: process.env.NODE_ENV,
  REACT_APP_WS_URL: process.env.REACT_APP_WS_URL,
  REACT_APP_API_BASE_URL: process.env.REACT_APP_API_BASE_URL,
  REACT_APP_ENV: process.env.REACT_APP_ENV,
  HOST: process.env.HOST,
  PORT: process.env.PORT,
  PUBLIC_URL: process.env.PUBLIC_URL,
  window_location: typeof window !== 'undefined' ? {
    hostname: window.location.hostname,
    port: window.location.port,
    protocol: window.location.protocol,
    href: window.location.href
  } : 'server-side'
});

// Create auth services using factory
const authServices = AuthFactory.createAuthServices();
const { deviceIdManager, tokenManager, localStorageService, sessionStorageService } = authServices;
logger.info('✅ Auth services created', { 
  hasTokenManager: !!tokenManager,
  hasDeviceIdManager: !!deviceIdManager 
});

// Initialize Rest APIs
const httpClient = new HttpClient(tokenManager);
const authApi = new AuthApi(httpClient);
const convictionsApi = new ConvictionsApi(httpClient);
logger.info('✅ API clients created');

// Set the auth API on token manager (important for token refresh!)
tokenManager.setAuthApi(authApi);
logger.info('✅ Auth API set on token manager');

// Initialize connection manager with dependency injection using the new websocket package
logger.info('🔌 Creating websocket dependencies...');
const { stateManager, toastService, configService } = createConnectionManagerWithGlobalDeps();
logger.info('✅ Websocket dependencies created', {
  hasStateManager: !!stateManager,
  hasToastService: !!toastService,
  hasConfigService: !!configService,
  wsUrl: configService.getWebSocketUrl(),
  reconnectionConfig: configService.getReconnectionConfig()
});

logger.info('🔌 Creating ConnectionManager...');
const connectionManager = new ConnectionManager(
  tokenManager,
  stateManager,
  toastService,
  configService
);
logger.info('✅ ConnectionManager created', { 
  connectionManager: !!connectionManager 
});

// Initialize conviction manager (remains the same)
const convictionManager = new ConvictionManager(
  convictionsApi, 
  tokenManager
);
logger.info('✅ ConvictionManager created');

logger.info('🎉 All services instantiated successfully');

// Log final WebSocket URL being used
logger.info('🔗 FINAL WEBSOCKET URL CHECK', {
  configServiceUrl: configService.getWebSocketUrl(),
  timestamp: new Date().toISOString()
});

// --- End Service Instantiation ---

function DeviceIdInvalidationHandler({ children }: { children: React.ReactNode }) {
  // websocket message "device_id_invalidated" routes user to session-deactivated Page
  const navigate = useNavigate();
  const { connectionManager } = useConnection();
  
  useEffect(() => {
    if (!connectionManager) {
      logger.warn('❌ No connectionManager in DeviceIdInvalidationHandler');
      return;
    }
    
    logger.info('🔌 Setting up device ID invalidation handler');
    
    const subscription = connectionManager.on('device_id_invalidated', (data) => {
      logger.error("🚨 DEVICE ID INVALIDATED - REDIRECTING TO SESSION DEACTIVATED PAGE", {
        data,
        currentPath: window.location.pathname,
        timestamp: new Date().toISOString()
      });
      
      navigate('/session-deactivated', { replace: true });
    });
    
    return () => {
      logger.info('🔌 Cleaning up device ID invalidation handler');
      subscription.unsubscribe();
    };
  }, [connectionManager, navigate]);
  
  return <>{children}</>;
}

// Add a debug component to check connection manager
function ConnectionDebugger() {
  const { connectionManager } = useConnection();
  
  useEffect(() => {
    logger.info('🔍 ConnectionDebugger: Checking connection manager', {
      hasConnectionManager: !!connectionManager,
      connectionManager
    });
    
    if (connectionManager) {
      // Add event listeners for debugging
      const subscriptions = [
        connectionManager.on('connected', () => {
          logger.info('🟢 CONNECTION DEBUG: Connected!');
        }),
        connectionManager.on('disconnected', (reason) => {
          logger.warn('🔴 CONNECTION DEBUG: Disconnected', { reason });
        }),
        connectionManager.on('error', (error) => {
          logger.error('❌ CONNECTION DEBUG: Error', { error });
        }),
        connectionManager.on('reconnecting', (attempt) => {
          logger.info('🔄 CONNECTION DEBUG: Reconnecting', { attempt });
        })
      ];
      
      return () => {
        subscriptions.forEach(sub => sub.unsubscribe());
      };
    }
  }, [connectionManager]);
  
  return null;
}

// Separate routes component for better organization
const AppRoutes: React.FC = () => {
  return (
    <>
      <ConnectionDebugger />
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
        
        {/* Protected routes with session */}
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

        <Route path="/profile/edit" element={
          <ProtectedRoute>
            <AuthenticatedLayout>
              <EditFundProfileForm />
            </AuthenticatedLayout>
          </ProtectedRoute>
        } />

        {/* Book routes */}
        <Route path="/books/new" element={
          <ProtectedRoute>
            <AuthenticatedLayout>
              <BookSetupPage />
            </AuthenticatedLayout>
          </ProtectedRoute>
        } />

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

        {/* Session deactivated page - note: not protected since user may be logged out */}
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
    </>
  );
};

function App() {
  useEffect(() => {
    logger.info('🎯 App component mounted, services available globally');
  }, []);

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