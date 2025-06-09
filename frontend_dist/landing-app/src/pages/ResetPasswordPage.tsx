// frontend_dist/landing-app/src/pages/ResetPasswordPage.tsx
import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import AuthLayout from './AuthLayout';
import { useToast } from '../hooks/useToast';
import { landingApiService } from '../api';
import { environmentService } from '../config/environment';
import './AuthForms.css';

const ResetPasswordPage: React.FC = () => {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [apiInitialized, setApiInitialized] = useState(false);
  const [authApiRef, setAuthApiRef] = useState<any>(null);
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
        
        const authApi = await landingApiService.getAuthApi();
        setAuthApiRef(authApi);
        setApiInitialized(true);
        
        if (environmentService.shouldLog()) {
          console.log('🔧 Reset Password API successfully initialized');
        }
      } catch (error) {
        console.error('❌ API initialization check failed:', error);
        setErrors({ 
          form: 'Failed to initialize authentication service. Please refresh the page.' 
        });
        addToast('error', 'Authentication service unavailable. Please refresh the page.');
      }
    };
    
    checkApiInitialization();
  }, [addToast]);

  // Extract token from URL query parameters
  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    const token = searchParams.get('token');
    
    if (!token) {
      addToast('error', 'Missing or invalid reset token');
      navigate('/forgot-password', { replace: true });
    } else {
      setToken(token);
      if (environmentService.shouldLog()) {
        console.log('🔧 Reset token extracted from URL');
      }
    }
  }, [location, addToast, navigate]);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    
    // Password validation
    if (!password) {
      newErrors.password = 'Password is required';
    } else if (password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    } else if (!/[A-Z]/.test(password)) {
      newErrors.password = 'Password must contain at least one uppercase letter';
    } else if (!/[a-z]/.test(password)) {
      newErrors.password = 'Password must contain at least one lowercase letter';
    } else if (!/[0-9]/.test(password)) {
      newErrors.password = 'Password must contain at least one number';
    } else if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
      newErrors.password = 'Password must contain at least one special character';
    }
    
    // Confirm password validation
    if (password !== confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!apiInitialized || !authApiRef) {
      setErrors({ 
        form: 'Authentication service not ready. Please refresh the page.' 
      });
      return;
    }

    if (!token) {
      setErrors({ 
        form: 'Missing reset token. Please request a new password reset link.' 
      });
      return;
    }
    
    if (!validateForm()) {
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const response = await authApiRef.resetPassword({
        token: token,
        newPassword: password
      });
      
      if (response.success) {
        setIsSuccess(true);
        addToast('success', 'Password has been reset successfully');
        
        if (environmentService.shouldLog()) {
          console.log('🔧 Password reset successful');
        }
      } else {
        setErrors({ 
          form: response.error || 'Failed to reset password. The link may have expired.' 
        });
        addToast('error', response.error || 'Failed to reset password');
      }
    } catch (error: any) {
      console.error('Reset password error:', error);
      setErrors({ 
        form: error.message || 'An error occurred during password reset. Please try again.' 
      });
      addToast('error', error.message || 'Error resetting password');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Function to get main app login URL
  const getMainAppLoginUrl = () => {
    const mainAppUrl = environmentService.getMainAppUrl();
    return `${mainAppUrl}/login`;
  };

  // Show loading state if API is not initialized
  if (!apiInitialized && !errors.form) {
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

  if (isSuccess) {
    return (
      <AuthLayout 
        title="Password Reset Complete" 
        subtitle="Your password has been reset successfully."
      >
        <div className="auth-success-message">
          <p>You can now log in with your new password.</p>
          <div className="auth-links">
            <a href={getMainAppLoginUrl()} className="auth-button">Go to Login</a>
          </div>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout 
      title="Reset Password" 
      subtitle="Create a new password for your account"
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        {errors.form && <div className="form-error">{errors.form}</div>}
        
        <div className="form-group">
          <label htmlFor="password">New Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={isSubmitting || !apiInitialized}
            placeholder="Create a new password"
            className={errors.password ? 'error' : ''}
          />
          {errors.password && <div className="field-error">{errors.password}</div>}
        </div>
        
        <div className="form-group">
          <label htmlFor="confirmPassword">Confirm Password</label>
          <input
            id="confirmPassword"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={isSubmitting || !apiInitialized}
            placeholder="Confirm your new password"
            className={errors.confirmPassword ? 'error' : ''}
          />
          {errors.confirmPassword && <div className="field-error">{errors.confirmPassword}</div>}
        </div>
        
        <button 
          type="submit" 
          className="auth-button" 
          disabled={isSubmitting || !apiInitialized}
        >
          {isSubmitting ? 'Resetting Password...' : 'Reset Password'}
        </button>
        
        <div className="auth-links">
          <p>Remember your password? <a href={getMainAppLoginUrl()}>Log in</a></p>
        </div>
      </form>
    </AuthLayout>
  );
};

export default ResetPasswordPage;