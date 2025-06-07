import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';

import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ForgotUsernamePage from './pages/ForgotUsernamePage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import EnterpriseContactPage from './pages/EnterpriseContactPage';

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <Routes>
          {/* Landing/Marketing Page */}
          <Route path="/" element={<LandingPage />} />
          
          {/* Authentication Pages */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/forgot-username" element={<ForgotUsernamePage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          
          {/* Public Pages */}
          <Route path="/enterprise-contact" element={<EnterpriseContactPage />} />
          
          {/* Redirect authenticated users to main app */}
          <Route path="/home" element={<RedirectToMainApp />} />
          <Route path="/app/*" element={<RedirectToMainApp />} />
        </Routes>
      </ThemeProvider>
    </BrowserRouter>
  );
}

// Component to redirect to main app
const RedirectToMainApp = () => {
  // Redirect to main app URL
  window.location.href = process.env.NODE_ENV === 'production' 
    ? 'https://app.digitaltrader.com' 
    : 'http://localhost:3000';
  return null;
};

export default App;