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

// API SERVICES - now from api package
import { ApiFactory } from '@trading-app/api';

// SERVICES - keep existing services that aren't API related
import { ConvictionManager } from './services/convictions/conviction-manager';

// CONTEXT
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';
import { AuthProvider } from './contexts/AuthContext';
import { TokenManagerProvider } from './contexts/TokenManagerContext';
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
import SessionDeactivatedPage from './pages/SessionDeactivatedPage';

import FundProfileForm from './components/Fund/FundProfileForm';
import EditFundProfileForm from './components/Fund/EditFundProfileForm';

import BookSetupPage from './components/Book/BookSetupPage';
import EditBookPage from './components/Book/EditBookPage';

// Initialize Logging First
initializeLogging();

// Create a logger for App.tsx debugging
const logger = getLogger('App');

// --- Helper functions for URL generation ---
function getLandingAppUrl(): string {
  // Use gateway routes for landing app
  return config.gateway?.routes?.home || 'http://localhost:8081/';
}

function getMainAppUrl(): string {
  // For main app, use the gateway dashboard route or construct from gateway base
  return config.gateway?.routes?.dashboard || `${config.gateway?.baseUrl || 'http://localhost:8081'}/home`;
}

function getBookAppUrl(): string {
  // For book app, use the gateway books route or construct from gateway base
  return config.gateway?.routes?.books || `${config.gateway?.baseUrl || 'http://localhost:8081'}/books`;
}

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
  gatewayBaseUrl: config.gateway?.baseUrl,
  mainAppUrl: getMainAppUrl(),
  landAppUrl: getLandingAppUrl(),
  bookAppUrl: getBookAppUrl(),
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
  logger.info('🔌 Main app: No WebSocket session management needed');
  
  return <>{children}</>;
}

// Separate routes component for better organization
const AppRoutes: React.FC = () => {
  return (
    <>
      <Routes>
        {/* These paths are relative to /app basename */}
        <Route path="/" element={<Navigate to="/home" replace />} />  {/* /app/ → /app/home */}
        <Route path="/login" element={<LoginPage />} />               {/* /app/login */}

        {/* Protected routes */}
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

        {/* Book routes - these will actually redirect to book app */}
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

        <Route path="/session-deactivated" element={              
            <AuthenticatedLayout>
              <SessionDeactivatedPage />
            </AuthenticatedLayout>
        } />

        {/* Default route */}
        <Route path="*" element={<Navigate to="/home" replace />} />
      </Routes>
    </>
  );
};

// Update the App function's Router section
function App() {
  useEffect(() => {
    logger.info('🎯 App component mounted, services available globally');
    logger.info('🔍 Current location:', {
      pathname: window.location.pathname,
      href: window.location.href,
      appType: config.appType
    });
  }, []);

  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider tokenManager={tokenManager} authApi={apiClients.auth}>
          <TokenManagerProvider tokenManager={tokenManager}>
            <BookManagerProvider bookClient={apiClients.book} tokenManager={tokenManager}>
              <ConvictionProvider convictionManager={convictionManager}>
                <FundProvider fundClient={apiClients.fund} tokenManager={tokenManager}>  
                  {/* Use Router without basename since proxy handles path rewriting */}
                  <Router basename="/app">
                    <DeviceIdInvalidationHandler>
                      <AppRoutes />
                    </DeviceIdInvalidationHandler>
                  </Router>
                </FundProvider>
              </ConvictionProvider>
            </BookManagerProvider>
          </TokenManagerProvider>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}

export default App;