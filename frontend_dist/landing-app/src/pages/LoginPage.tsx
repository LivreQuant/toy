// landing-app/src/pages/LoginPage.tsx
import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useToast } from '../hooks/useToast';
import AuthLayout from './AuthLayout';
import { landingApiService } from '../api';
import { environmentService } from '../config';
import './AuthForms.css';

interface LocationState {
  verified?: boolean;
  from?: string;
  userId?: string | number;
  needsVerification?: boolean;
}

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiInitialized, setApiInitialized] = useState(false);
  const [loginStage, setLoginStage] = useState<'idle' | 'authenticating' | 'storing_tokens' | 'redirecting'>('idle');
  
  const { addToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  
  // Check API initialization on component mount
  useEffect(() => {
    const checkApiInitialization = async () => {
      try {
        const isHealthy = await landingApiService.healthCheck();
        
        if (!isHealthy) {
          throw new Error('API health check failed');
        }
        
        setApiInitialized(true);
        
        if (environmentService.shouldLog()) {
          console.log('🔧 Login API successfully initialized');
        }
      } catch (error) {
        console.error('❌ API initialization check failed:', error);
        setError('Failed to initialize authentication service. Please refresh the page.');
        addToast('error', 'Authentication service unavailable. Please refresh the page.');
      }
    };
    
    checkApiInitialization();
  }, [addToast]);
  
  // Check for redirect state
  useEffect(() => {
    const state = location.state as LocationState;
    
    if (state?.verified) {
      addToast('success', 'Email verified successfully! You can now log in.');
    }
  }, [location, addToast]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!apiInitialized) {
      setError('Authentication service not ready. Please refresh the page.');
      return;
    }
    
    if (environmentService.shouldLog()) {
      console.log("🔍 LOGIN: Submit button clicked");
    }
    
    if (!username.trim() || !password) {
      setError('Please enter both username and password');
      if (environmentService.shouldLog()) {
        console.log("🔍 LOGIN: Missing username or password");
      }
      return;
    }
    
    setError(null);
    setIsSubmitting(true);
    setLoginStage('authenticating');
    
    if (environmentService.shouldLog()) {
      console.log("🔍 LOGIN: Starting login process for user:", username);
    }
    
    try {
      setLoginStage('authenticating');
      
      if (environmentService.shouldLog()) {
        console.log("🔍 LOGIN: Calling login API with token storage");
      }
      
      const response = await landingApiService.loginAndStoreTokens(username, password);
      
      if (environmentService.shouldLog()) {
        console.log("🔍 LOGIN: Got response from login API:", {
          success: response.success,
          requiresVerification: response.requiresVerification,
          tokensStored: response.tokensStored
        });
      }
      
      // Check for verification required case
      if (response.requiresVerification && response.userId) {
        if (environmentService.shouldLog()) {
          console.log("🔍 LOGIN: Email verification required, userId:", response.userId);
        }
        
        const verificationState = { 
          userId: response.userId,
          needsVerification: true
        };
        
        if ('email' in response) {
          (verificationState as any).email = response.email;
        }
        
        if (environmentService.shouldLog()) {
          console.log("🔍 LOGIN: Navigating to verification page");
        }
        
        navigate(`/verify-email?userId=${response.userId}`, {
          state: verificationState
        });
        
        addToast('warning', 'Please verify your email address before logging in.');
        return;
      }
      
      if (response.success && response.tokensStored) {
        setLoginStage('redirecting');
        
        if (environmentService.shouldLog()) {
          console.log("🔍 LOGIN: Login successful and tokens stored, redirecting to main app");
        }
        
        // Add a small delay to ensure all state is settled
        setTimeout(() => {
          // REDIRECT TO MAIN APP AFTER SUCCESSFUL LOGIN AND TOKEN STORAGE
          const mainAppUrl = environmentService.getMainAppUrl();
          const redirectPath = '/home'; // Main app landing page
          const fullUrl = `${mainAppUrl}${redirectPath}`;
          
          if (environmentService.shouldLog()) {
            console.log(`🔗 Tokens secured and verified, redirecting to main app: ${fullUrl}`);
          }
          
          // Force redirect to main app
          window.location.href = fullUrl;
        }, 200);
        
      } else if (response.success && !response.tokensStored) {
        // This shouldn't happen, but handle it gracefully
        setError('Login successful but failed to store credentials. Please try again.');
        if (environmentService.shouldLog()) {
          console.error("🔍 LOGIN: Login succeeded but tokens not stored");
        }
      } else {
        if (environmentService.shouldLog()) {
          console.log("🔍 LOGIN: Login failed:", response.error);
        }
        setError(response.error || 'Invalid username or password');
      }
    } catch (error: any) {
      console.error("🔍 LOGIN: Exception during login:", error);
      setError(error.message || 'Login failed. Please try again.');
      setLoginStage('idle');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Show loading state if API is not initialized
  if (!apiInitialized && !error) {
    return (
      <AuthLayout 
        title="Loading..." 
        subtitle="Initializing authentication service"
      >
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <div style={{ marginBottom: '10px' }}>Please wait...</div>
        </div>
      </AuthLayout>
    );
  }

  // Dynamic subtitle based on login stage
  const getSubtitle = () => {
    switch (loginStage) {
      case 'authenticating':
        return 'Authenticating credentials...';
      case 'storing_tokens':
        return 'Securing your session...';
      case 'redirecting':
        return 'Redirecting to application...';
      default:
        return 'Welcome back to DigitalTrader';
    }
  };

  return (
    <AuthLayout 
      title="Log In" 
      subtitle={getSubtitle()}
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}
        
        <div className="form-group">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={isSubmitting || !apiInitialized}
            placeholder="Enter your username"
            autoFocus
          />
        </div>
        
        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isSubmitting || !apiInitialized}
            placeholder="Enter your password"
          />
        </div>
        
        <button 
          type="submit" 
          className="auth-button" 
          disabled={isSubmitting || !apiInitialized}
        >
          {isSubmitting ? getButtonText() : 'Log In'}
        </button>
        
        <div className="auth-links">
          <p>Don't have an account? <Link to="/signup">Sign up</Link></p>
          <p>Forgot your username? <Link to="/forgot-username">Recover username</Link></p>
          <p>Forgot your password? <Link to="/forgot-password">Reset password</Link></p>
        </div>
      </form>
    </AuthLayout>
  );

  function getButtonText() {
    switch (loginStage) {
      case 'authenticating':
        return 'Authenticating...';
      case 'storing_tokens':
        return 'Securing Session...';
      case 'redirecting':
        return 'Redirecting...';
      default:
        return 'Logging in...';
    }
  }
};

export default LoginPage;