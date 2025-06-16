// frontend_dist/landing-app/src/App.tsx
import React, { useEffect, useState } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';

import LandingPage from './pages/LandingPage';
import SignupPage from './pages/SignupPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ForgotUsernamePage from './pages/ForgotUsernamePage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import EnterpriseContactPage from './pages/EnterpriseContactPage';

import { environmentService } from './config';
import { credentialChecker } from './services/credential-checker';
import LoadingSpinner from './components/Common/LoadingSpinner';

function App() {
  const [isCheckingCredentials, setIsCheckingCredentials] = useState(true);
  const [credentialCheckComplete, setCredentialCheckComplete] = useState(false);

  useEffect(() => {
    const checkCredentialsAndRedirect = async () => {
      try {
        if (environmentService.shouldLog()) {
          console.log('🚀 Landing App initialized, checking stored credentials...');
        }

        // Check if user has valid stored credentials
        const result = await credentialChecker.checkStoredCredentials();

        if (result.shouldRedirect && result.redirectUrl) {
          if (environmentService.shouldLog()) {
            console.log('🔗 Valid credentials found, redirecting to main app');
          }
          
          // Don't set credentialCheckComplete - just redirect immediately
          credentialChecker.redirectToMainApp(result.redirectUrl);
          return; // Don't continue with normal app rendering
        }

        if (environmentService.shouldLog()) {
          console.log('🔍 No valid credentials found, proceeding with landing app');
        }

      } catch (error) {
        console.error('❌ Error during credential check:', error);
      } finally {
        setIsCheckingCredentials(false);
        setCredentialCheckComplete(true);
      }
    };

    checkCredentialsAndRedirect();
  }, []);

  // Show loading spinner while checking credentials
  if (isCheckingCredentials) {
    return (
      <LoadingSpinner message="Checking credentials..." />
    );
  }

  // Only render the app once credential check is complete
  if (!credentialCheckComplete) {
    return null;
  }

  return (
    <BrowserRouter>
      <ThemeProvider>
        <ToastProvider>
          <Routes>
            {/* LANDING APP ROUTES ONLY */}
            <Route path="/" element={<LandingPage />} />
            
            {/* AUTH ROUTES - HANDLED BY LANDING APP (except login) */}
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/forgot-username" element={<ForgotUsernamePage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            
            {/* PUBLIC PAGES */}
            <Route path="/enterprise-contact" element={<EnterpriseContactPage />} />
            
          </Routes>
        </ToastProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;