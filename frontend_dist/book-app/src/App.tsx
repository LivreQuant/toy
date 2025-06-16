// frontend_dist/book-app/src/App.tsx
import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';

// Use unified config instead of local environment service
import { config, isBookApp, shouldLog } from '@trading-app/config';

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

// COMPONENTS
import ProtectedRoute from './components/Common/ProtectedRoute';

// LAYOUT 
import AuthenticatedLayout from './components/Layout/AuthenticatedLayout';

// PAGES
import SimulatorPage from './pages/SimulatorPage';
import BookDetailsPage from './pages/BookDetailsPage';
import SessionDeactivatedPage from './pages/SessionDeactivatedPage';

// Initialize Logging First
initializeLogging();

// Create a logger for App.tsx debugging
const logger = getLogger('BookApp');

// Redirecting Component for when authentication is missing
const RedirectingToMainApp: React.FC<{ reason: string }> = ({ reason }) => {
  const mainAppUrl = config.main.baseUrl;
  const redirectUrl = `${mainAppUrl}/login`;
  
  useEffect(() => {
    logger.info('🔗 BOOK APP: Redirecting to main app', { reason, redirectUrl });
    // Small delay to show the message
    const timer = setTimeout(() => {
      window.location.href = redirectUrl;
    }, 2000);
    
    return () => clearTimeout(timer);
  }, [reason, redirectUrl]);
  
  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center', 
      justifyContent: 'center', 
      height: '100vh',
      textAlign: 'center',
      padding: '20px',
      fontFamily: 'Arial, sans-serif'
    }}>
      <h2>Redirecting to Main App</h2>
      <p>{reason}</p>
      <p style={{ marginTop: '20px', color: '#666' }}>
        Taking you to the main app in 2 seconds...
      </p>
      <p style={{ marginTop: '10px', color: '#666' }}>
        If you're not redirected automatically, <a href={redirectUrl}>click here</a>
      </p>
    </div>
  );
};

// Check authentication status and return appropriate component
function checkAuthenticationStatus(): { 
  isValid: boolean, 
  reason?: string,
  authServices?: any,
  apiClients?: any,
  connectionManager?: any,
  convictionManager?: any 
} {
  // Validate we're running the right app
  if (!isBookApp()) {
    logger.warn('⚠️ Book app detected non-book app configuration!');
  }

  // Log environment information for debugging using unified config
  logger.info('🔍 BOOK APP STARTUP: Environment information', {
    appType: config.appType,
    environment: config.environment,
    apiBaseUrl: config.apiBaseUrl,
    wsUrl: config.websocket.url,
    mainAppUrl: config.main.baseUrl,
    bookAppUrl: config.book.baseUrl,
    landAppUrl: config.land.baseUrl,
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

  // 🔒 BOOK APP SECURITY CHECK: Prevent book app from running without main app authentication
  if (!deviceIdManager.hasStoredDeviceId()) {
    logger.warn('🔒 BOOK APP: No device ID found - user must authenticate in main app first');
    return { 
      isValid: false, 
      reason: 'No device ID found. Please authenticate in the main app first.' 
    };
  }

  if (!tokenManager.isAuthenticated()) {
    logger.warn('🔒 BOOK APP: No valid authentication found - redirecting to main app');
    return { 
      isValid: false, 
      reason: 'Valid authentication required. Taking you to the main app to log in.' 
    };
  }

  logger.info('✅ BOOK APP: Authentication validated - proceeding with initialization');

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

  return {
    isValid: true,
    authServices,
    apiClients,
    connectionManager,
    convictionManager
  };
}

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
        {/* Protected routes with session */}
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

        {/* Default route - Redirect to main app */}
        <Route path="*" element={<RedirectToMainApp />} />
      </Routes>
    </>
  );
};

// Component to redirect to main app
const RedirectToMainApp: React.FC = () => {
  const currentPath = window.location.pathname + window.location.search;
  const mainAppUrl = config.main.baseUrl;
  
  React.useEffect(() => {
    console.log(`🔗 Redirecting ${currentPath} to main app: ${mainAppUrl}${currentPath}`);
    window.location.href = `${mainAppUrl}${currentPath}`;
  }, [currentPath, mainAppUrl]);
  
  return (
    <div style={{ textAlign: 'center', padding: '50px' }}>
      <h2>Redirecting...</h2>
      <p>Taking you to {mainAppUrl}{currentPath}</p>
    </div>
  );
};

// Main authenticated app component
const AuthenticatedApp: React.FC<{
  authServices: any,
  apiClients: any,
  connectionManager: any,
  convictionManager: any
}> = ({ authServices, apiClients, connectionManager, convictionManager }) => {
  const { tokenManager } = authServices;

  useEffect(() => {
    logger.info('🎯 Book App component mounted, services available globally');
  }, []);

  return (
    <ThemeProvider>
      <ToastProvider>
        <AuthProvider tokenManager={tokenManager} authApi={apiClients.auth} connectionManager={connectionManager}>
          <TokenManagerProvider tokenManager={tokenManager}>
            <BookManagerProvider bookClient={apiClients.book} tokenManager={tokenManager}>
              <ConvictionProvider convictionManager={convictionManager}>
                <ConnectionProvider connectionManager={connectionManager}>
                  <Router>
                    <DeviceIdInvalidationHandler>
                      <AppRoutes />
                    </DeviceIdInvalidationHandler>
                  </Router>
                </ConnectionProvider>
              </ConvictionProvider>
            </BookManagerProvider>
          </TokenManagerProvider>
        </AuthProvider>
      </ToastProvider>
    </ThemeProvider>
  );
};

function App() {
  // Always call hooks at the top level
  const [authResult, setAuthResult] = useState<{
    isValid: boolean,
    reason?: string,
    authServices?: any,
    apiClients?: any,
    connectionManager?: any,
    convictionManager?: any
  } | null>(null);

  // Check authentication status on mount
  useEffect(() => {
    const result = checkAuthenticationStatus();
    setAuthResult(result);
  }, []);

  // Show loading while checking authentication
  if (!authResult) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh',
        fontFamily: 'Arial, sans-serif'
      }}>
        <div>Initializing Book App...</div>
      </div>
    );
  }
  
  // If authentication is invalid, show redirect component
  if (!authResult.isValid) {
    return <RedirectingToMainApp reason={authResult.reason!} />;
  }
  
  // Render the authenticated app
  return (
    <AuthenticatedApp
      authServices={authResult.authServices}
      apiClients={authResult.apiClients}
      connectionManager={authResult.connectionManager}
      convictionManager={authResult.convictionManager}
    />
  );
}

export default App;