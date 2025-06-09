import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate, useSearchParams, Link } from 'react-router-dom';
import AuthLayout from './AuthLayout';
import { useToast } from '../hooks/useToast';
import { getAuthApi } from '../api';
import { environmentService } from '../config/environment';
import './AuthForms.css';

interface LocationState {
  userId?: string | number;
  email?: string;
  needsVerification?: boolean;
}

const VerifyEmailPage: React.FC = () => {
  const [verificationCode, setVerificationCode] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [apiInitialized, setApiInitialized] = useState(false);
  const [authApiRef, setAuthApiRef] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Add search params to support query string parameters
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { addToast } = useToast();
  
  // Extract state passed from signup/login AND check URL query params as fallback
  const locationState = location.state as LocationState;
  const userId = locationState?.userId || searchParams.get('userId') || '';
  const email = locationState?.email || searchParams.get('email') || '';
  const needsVerification = locationState?.needsVerification || searchParams.get('needsVerification') === 'true';

  // Check API initialization on component mount
  useEffect(() => {
    const checkApiInitialization = async () => {
      try {
        const authApi = await getAuthApi();
        
        if (!authApi || typeof authApi.verifyEmail !== 'function' || typeof authApi.resendVerification !== 'function') {
          throw new Error('Auth API missing required methods');
        }
        
        setAuthApiRef(authApi);
        setApiInitialized(true);
        
        if (environmentService.shouldLog()) {
          console.log('🔧 Verify Email API successfully initialized');
        }
      } catch (error) {
        console.error('❌ API initialization check failed:', error);
        setError('Failed to initialize authentication service. Please refresh the page.');
        addToast('error', 'Authentication service unavailable. Please refresh the page.');
      }
    };
    
    checkApiInitialization();
  }, [addToast]);
  
  useEffect(() => {
    // Redirect if no userId found - with more detailed error
    if (!userId) {
      console.error("Missing verification info:", { 
        hasState: !!location.state,
        locationUserId: locationState?.userId,
        locationEmail: locationState?.email,
        queryUserId: searchParams.get('userId'),
        queryEmail: searchParams.get('email')
      });
      
      addToast('error', 'Missing information required for verification. Please try signing up again.');
      navigate('/signup', { replace: true });
    }
  }, [userId, email, addToast, navigate, location.state, searchParams, locationState]);
  
  // Handle resend cooldown timer
  useEffect(() => {
    let timerId: number;
    if (resendCooldown > 0) {
      timerId = window.setTimeout(() => {
        setResendCooldown(prev => prev - 1);
      }, 1000);
    }
    return () => {
      if (timerId) clearTimeout(timerId);
    };
  }, [resendCooldown]);

  const handleCodeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Only allow numbers
    const value = e.target.value.replace(/\D/g, '');
    setVerificationCode(value);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!apiInitialized || !authApiRef) {
      setError('Authentication service not ready. Please refresh the page.');
      return;
    }
    
    if (!verificationCode.trim()) {
      addToast('warning', 'Please enter the verification code');
      return;
    }

    if (!userId) {
      addToast('error', 'Missing user information. Please try signing up again.');
      navigate('/signup', { replace: true });
      return;
    }
    
    setIsSubmitting(true);
    setError(null);
    
    try {
      const response = await authApiRef.verifyEmail({
        userId: userId,
        code: verificationCode
      });
      
      if (response.success) {
        addToast('success', 'Email verified successfully!');
        navigate('/login', { 
          state: { verified: true } 
        });
        
        if (environmentService.shouldLog()) {
          console.log('🔧 Email verification successful');
        }
      } else {
        addToast('error', response.error || 'Invalid verification code');
        setError(response.error || 'Invalid verification code');
      }
    } catch (error: any) {
      console.error('Email verification error:', error);
      const errorMessage = error.message || 'Error verifying email';
      addToast('error', errorMessage);
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendCode = async () => {
    if (resendCooldown > 0 || !apiInitialized || !authApiRef) return;

    if (!userId) {
      addToast('error', 'Missing user information. Please try signing up again.');
      navigate('/signup', { replace: true });
      return;
    }
    
    setIsResending(true);
    setError(null);
    
    try {
      const response = await authApiRef.resendVerification({
        userId: userId
      });
      
      if (response.success) {
        addToast('success', 'A new verification code has been sent to your email');
        setResendCooldown(60); // 60 seconds cooldown
        
        if (environmentService.shouldLog()) {
          console.log('🔧 Verification code resent successfully');
        }
      } else {
        const errorMessage = response.error || 'Failed to resend verification code';
        addToast('error', errorMessage);
        setError(errorMessage);
      }
    } catch (error: any) {
      console.error('Resend verification error:', error);
      const errorMessage = error.message || 'Error requesting new code';
      addToast('error', errorMessage);
      setError(errorMessage);
    } finally {
      setIsResending(false);
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

  return (
    <AuthLayout 
      title="Verify Your Email" 
      subtitle={email ? 
        `We've sent a verification code to ${email}. Please check your inbox.` : 
        "We've sent a verification code to your email. Please check your inbox."
      }
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        {error && <div className="form-error">{error}</div>}
        
        <div className="form-group verification-code-group">
          <label htmlFor="verificationCode">Verification Code</label>
          <input
            id="verificationCode"
            type="text"
            value={verificationCode}
            onChange={handleCodeChange}
            disabled={isSubmitting || !apiInitialized}
            placeholder="Enter 6-digit code"
            maxLength={6}
            autoFocus
          />
        </div>
        
        <button 
          type="submit" 
          className="auth-button" 
          disabled={isSubmitting || verificationCode.length !== 6 || !apiInitialized}
        >
          {isSubmitting ? 'Verifying...' : 'Verify Email'}
        </button>
        
        <div className="auth-links">
          <button 
            type="button" 
            className="text-button"
            onClick={handleResendCode}
            disabled={isResending || resendCooldown > 0 || !apiInitialized}
          >
            {resendCooldown > 0 
              ? `Resend code in ${resendCooldown}s` 
              : isResending 
                ? 'Resending...' 
                : "Didn't receive a code? Resend"
            }
          </button>
        </div>
        
        <div className="auth-links">
          <p>Need to use a different email? <Link to="/signup">Sign up again</Link></p>
        </div>
      </form>
    </AuthLayout>
  );
};

export default VerifyEmailPage;