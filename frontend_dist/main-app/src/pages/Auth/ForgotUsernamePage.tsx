// frontend_dist/main-app/src/pages/Auth/ForgotUsernamePage.tsx
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import AuthLayout from './AuthLayout';
import { useToast } from '../../hooks/useToast';
import './AuthForms.css';

// Import API client from new package
import { ApiFactory } from '@trading-app/api';
import { AuthFactory } from '@trading-app/auth';

const ForgotUsernamePage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const { addToast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!email.trim() || !/\S+@\S+\.\S+/.test(email)) {
      addToast('warning', 'Please enter a valid email address');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      // Create a temporary auth client for this request
      const authServices = AuthFactory.createAuthServices();
      const authApi = ApiFactory.createAuthClient(authServices.tokenManager);
      
      const response = await authApi.forgotUsername({ email });
      
      // For security reasons, the API always returns success
      // to avoid revealing if an email exists in the system
      setIsSubmitted(true);
      addToast('success', 'If your email is registered, you will receive your username shortly');
    } catch (error: any) {
      // Still show success message even on error for security
      setIsSubmitted(true);
      addToast('success', 'If your email is registered, you will receive your username shortly');
      
      // Log the error but don't display to user
      console.error('Error requesting username:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSubmitted) {
    return (
      <AuthLayout 
        title="Check Your Email" 
        subtitle="If your email is registered, you will receive your username details shortly."
      >
        <div className="auth-success-message">
          <p>Please check your inbox for an email containing your username.</p>
          <div className="auth-links">
            <Link to="/login" className="auth-button">Return to Login</Link>
          </div>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout 
      title="Forgot Username" 
      subtitle="Enter your email to receive your username"
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="email">Email Address</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={isSubmitting}
            placeholder="Enter your email address"
            required
          />
        </div>
        
        <button 
          type="submit" 
          className="auth-button" 
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Submitting...' : 'Request Username'}
        </button>
        
        <div className="auth-links">
          <p>Remember your username? <Link to="/login">Log in</Link></p>
          <p>Don't have an account? <Link to="/signup">Sign up</Link></p>
        </div>
      </form>
    </AuthLayout>
  );
};

export default ForgotUsernamePage;