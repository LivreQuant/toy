// frontend_dist/main-app/src/App.tsx
import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';

// Use unified config instead of local environment service
import { config, isMainApp, shouldLog } from '@trading-app/config';

// LOGGING - now from package
import { initializeLogging, getLogger } from '@trading-app/logging';

// AUTH SERVICES - now from auth package
import { AuthFactory, DeviceIdManager, TokenManager } from '@trading-app/auth';

// WEBSOCKET SERVICES - now from websocket package
import { 
  ConnectionManager, 
  createConnectionManagerWithGlobalDeps 
} from '@trading-app/websocket';

// API SERVICES - now from api package
import { ApiFactory } from '@trading-app/api';

// SERVICES - keep existing services that aren't API related
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
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import SimulatorPage from './pages/SimulatorPage';
import BookDetailsPage from './pages/BookDetailsPage';
import SessionDeactivatedPage from './pages/SessionDeactivatedPage';

import FundProfileForm from './components/Fund/FundProfileForm';
import EditFundProfileForm from './components/Fund/EditFundProfileForm';

import BookSetupPage from './components/Book/BookSetupPage';
import EditBookPage from './components/Book/EditBookPage';

// Initialize Logging First
initializeLogging();

// Create a logger for App.tsx debugging
const logger = getLogger('App');

// --- Start Service Instantiation ---

logger.info('🚀 Starting service instantiation...');

// Validate we're running the right app
if (!isMainApp()) {
  logger.warn('⚠️ Main app detected non-main app configuration!');
}

// Log environment information for debugging using unified config
logger.info('🔍 APP STARTUP: Environment information', {
  appType: config.appType,
  environment: config.environment,
  apiBaseUrl: config.apiBaseUrl,
  wsUrl: config.websocket.url,
  mainAppUrl: config.main.baseUrl,
  landingUrl: config.landing.baseUrl,
  NODE_ENV: process.env.NODE_ENV,
  REACT_APP_API_BASE_URL: process.env.REACT_APP_API_BASE_URL,
  REACT_APP_WS_URL: process.env.REACT_APP_WS_URL,
  REACT_APP_ENV: process.env.REACT_APP_ENV,
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

// Create API clients using factory
const apiClients = ApiFactory.createClients(tokenManager);
logger.info('✅ API clients created with base URL:', config.apiBaseUrl);

// Set the auth API on token manager (important for token refresh!)
tokenManager.setAuthApi(apiClients.auth);
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

// Initialize conviction manager (now uses new API client)
const convictionManager = new ConvictionManager(
  apiClients.conviction, 
  tokenManager
);
logger.info('✅ ConvictionManager created');

logger.info('🎉 All services instantiated successfully');

// Log final API URL being used
logger.info('🔗 FINAL API URL CHECK', {
  configApiUrl: config.apiBaseUrl,
  envApiUrl: process.env.REACT_APP_API_BASE_URL,
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

// Separate routes component for better organization
const AppRoutes: React.FC = () => {
  return (
    <>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<Navigate to="/home" replace />} />
        <Route path="/login" element={<LoginPage />} />

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
        <AuthProvider tokenManager={tokenManager} authApi={apiClients.auth} connectionManager={connectionManager}>
          <TokenManagerProvider tokenManager={tokenManager}>
            <BookManagerProvider bookClient={apiClients.book} tokenManager={tokenManager}>
              <ConvictionProvider convictionManager={convictionManager}>
                <ConnectionProvider connectionManager={connectionManager}>
                  <FundProvider fundClient={apiClients.fund} tokenManager={tokenManager}>  
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

// Add redirect component
/*
const RedirectToLanding: React.FC = () => {
  const currentPath = window.location.pathname + window.location.search;
  const landingUrl = config.landing.baseUrl;
  
  React.useEffect(() => {
    console.log(`🔗 Redirecting ${currentPath} to landing app: ${landingUrl}${currentPath}`);
    window.location.href = `${landingUrl}${currentPath}`;
  }, [currentPath, landingUrl]);
  
  return (
    <div style={{ textAlign: 'center', padding: '50px' }}>
      <h2>Redirecting...</h2>
      <p>Taking you to {landingUrl}{currentPath}</p>
    </div>
  );
};
*/

export default App;