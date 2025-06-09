// frontend_dist/landing-app/src/App.tsx
import React, { useEffect } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';

import LandingPage from './pages/LandingPage';
// Remove LoginPage import
import SignupPage from './pages/SignupPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ForgotUsernamePage from './pages/ForgotUsernamePage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import EnterpriseContactPage from './pages/EnterpriseContactPage';

import { environmentService } from './config';

function App() {
  useEffect(() => {
    if (environmentService.shouldLog()) {
      console.log('🚀 Landing App initialized');
    }
  }, []);

  return (
    <BrowserRouter>
      <ThemeProvider>
        <ToastProvider>
          <Routes>
            {/* LANDING APP ROUTES ONLY */}
            <Route path="/" element={<LandingPage />} />
            
            {/* AUTH ROUTES - HANDLED BY LANDING APP (except login) */}
            {/* Login is now handled by main app */}
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/forgot-username" element={<ForgotUsernamePage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            
            {/* PUBLIC PAGES */}
            <Route path="/enterprise-contact" element={<EnterpriseContactPage />} />
            
            {/* 
              ANY OTHER ROUTE = REDIRECT TO MAIN APP
              This catches /login, /home, /profile, /books, /simulator, etc.
            */}
            <Route path="*" element={<RedirectToMainApp />} />
          </Routes>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

// Redirect component for authenticated routes and login
const RedirectToMainApp: React.FC = () => {
  const currentPath = window.location.pathname;
  const mainAppUrl = environmentService.getMainAppUrl();
  
  React.useEffect(() => {
    console.log(`🔗 Redirecting ${currentPath} to main app`);
    window.location.href = `${mainAppUrl}${currentPath}`;
  }, [currentPath, mainAppUrl]);
  
  return (
    <div style={{ 
      textAlign: 'center', 
      padding: '50px',
      maxWidth: '600px',
      margin: '0 auto',
    }}>
      <h2>Redirecting to Application...</h2>
      <p>Taking you to the main application...</p>
      <div style={{ 
        marginTop: '20px', 
        padding: '10px', 
        backgroundColor: '#f8f9fa', 
        borderRadius: '4px',
        fontSize: '0.9rem',
        color: '#666'
      }}>
        Target: {mainAppUrl}{currentPath}
      </div>
    </div>
  );
};

export default App;