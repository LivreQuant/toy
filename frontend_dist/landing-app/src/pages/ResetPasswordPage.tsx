import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import AuthLayout from './AuthLayout';
import { useToast } from '../hooks/useToast';
import './AuthForms.css';

// Import API client
import { authApi } from '../api';


const ResetPasswordPage: React.FC = () => {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const { addToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();

  // Extract token from URL query parameters
  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    const token = searchParams.get('token');
    
    if (!token) {
      addToast('error', 'Missing or invalid reset token');
      navigate('/forgot-password', { replace: true });
    } else {
      setToken(token);
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
    
    if (!validateForm()) {
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const response = await authApi.resetPassword({
        token: token!,
        newPassword: password
      });
      
      if (response.success) {
        setIsSuccess(true);
        addToast('success', 'Password has been reset successfully');
      } else {
        setErrors({ 
          form: response.error || 'Failed to reset password. The link may have expired.' 
        });
        addToast('error', response.error || 'Failed to reset password');
      }
    } catch (error: any) {
      setErrors({ 
        form: error.message || 'An error occurred during password reset. Please try again.' 
      });
      addToast('error', error.message || 'Error resetting password');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSuccess) {
    return (
      <AuthLayout 
        title="Password Reset Complete" 
        subtitle="Your password has been reset successfully."
      >
        <div className="auth-success-message">
          <p>You can now log in with your new password.</p>
          <div className="auth-links">
            <Link to="/login" className="auth-button">Go to Login</Link>
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
            disabled={isSubmitting}
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
            disabled={isSubmitting}
            placeholder="Confirm your new password"
            className={errors.confirmPassword ? 'error' : ''}
          />
          {errors.confirmPassword && <div className="field-error">{errors.confirmPassword}</div>}
        </div>
        
        <button 
          type="submit" 
          className="auth-button" 
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Resetting Password...' : 'Reset Password'}
        </button>
      </form>
    </AuthLayout>
  );
};

export default ResetPasswordPage;