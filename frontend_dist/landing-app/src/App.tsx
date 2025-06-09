import React, { useEffect } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';

import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ForgotUsernamePage from './pages/ForgotUsernamePage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import EnterpriseContactPage from './pages/EnterpriseContactPage';

import { environmentService, appUrlService } from './config';

function App() {
  // Initialize and validate environment on app start
  useEffect(() => {
    if (environmentService.shouldLog()) {
      console.log('🚀 Landing App initialized with environment:', {
        ...environmentService.getConfig(),
        domainInfo: appUrlService.getCurrentDomainInfo(),
      });
    }

    // Optional: Perform API health check on startup
    if (environmentService.shouldDebug()) {
      import('./api').then(({ getApiInfo }) => {
        const apiInfo = getApiInfo();
        console.log('🔧 API Info:', apiInfo);
      });
    }
  }, []);

  return (
    <BrowserRouter>
      <ThemeProvider>
        <ToastProvider>
          <Routes>
            {/* Landing/Marketing Page */}
            <Route path="/" element={<LandingPage />} />
            
            {/* Authentication Pages - Keep in landing app */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/forgot-username" element={<ForgotUsernamePage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            
            {/* Public Pages */}
            <Route path="/enterprise-contact" element={<EnterpriseContactPage />} />
            
            {/* Redirect authenticated routes to main app */}
            <Route path="/home" element={<RedirectToMainApp path="/home" />} />
            <Route path="/app/*" element={<RedirectToMainApp path="/app" />} />
            <Route path="/profile/*" element={<RedirectToMainApp path="/profile" />} />
            <Route path="/books/*" element={<RedirectToMainApp path="/books" />} />
            <Route path="/simulator/*" element={<RedirectToMainApp path="/simulator" />} />
            
            {/* Catch all - redirect to landing */}
            <Route path="*" element={<LandingPage />} />
          </Routes>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

// Component to redirect to main app
const RedirectToMainApp: React.FC<{ path: string }> = ({ path }) => {
  const mainAppUrl = environmentService.getMainAppUrl();
  
  React.useEffect(() => {
    appUrlService.redirectToMainApp(path);
  }, [path]);
  
  return (
    <div style={{ 
      textAlign: 'center', 
      padding: '50px',
      maxWidth: '600px',
      margin: '0 auto',
    }}>
      <h2>Redirecting to Application...</h2>
      <p>
        If you are not redirected automatically,{' '}
        <a href={`${mainAppUrl}${path}`} style={{ color: '#3498db' }}>
          click here
        </a>
        .
      </p>
      <div style={{ 
        marginTop: '20px', 
        padding: '10px', 
        backgroundColor: '#f8f9fa', 
        borderRadius: '4px',
        fontSize: '0.9rem',
        color: '#666'
      }}>
        Environment: {environmentService.getAppConfig().environment}<br />
        Target: {mainAppUrl}{path}
      </div>
    </div>
  );
};

export default App;