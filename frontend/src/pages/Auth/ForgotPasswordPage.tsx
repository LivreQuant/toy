import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import AuthLayout from './AuthLayout';
import { useAuth } from '../../hooks/useAuth';
import { useToast } from '../../hooks/useToast';
import './AuthForms.css';

// Import API client

const ForgotPasswordPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const { addToast } = useToast();

  const { forgotPassword, isAuthenticated } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!email.trim() || !/\S+@\S+\.\S+/.test(email)) {
      addToast('warning', 'Please enter a valid email address');
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const response = await forgotPassword({ email });
      
      // For security reasons, the API always returns success
      // to avoid revealing if an email exists in the system
      setIsSubmitted(true);
      addToast('success', 'If your email is registered, you will receive a password reset link shortly');
    } catch (error: any) {
      // Still show success message even on error for security
      setIsSubmitted(true);
      addToast('success', 'If your email is registered, you will receive a password reset link shortly');
      
      // Log the error but don't display to user
      console.error('Error requesting password reset:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSubmitted) {
    return (
      <AuthLayout 
        title="Check Your Email" 
        subtitle="If your email is registered, we've sent password reset instructions."
      >
        <div className="auth-success-message">
          <p>Please check your inbox for an email with a link to reset your password.</p>
          <div className="auth-links">
            <Link to="/login" className="auth-button">Return to Login</Link>
          </div>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout 
      title="Forgot Password" 
      subtitle="Enter your email address to receive a password reset link"
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
          {isSubmitting ? 'Submitting...' : 'Reset Password'}
        </button>
        
        <div className="auth-links">
          <p>Forgot your username? <Link to="/forgot-username">Recover username</Link></p>
          <p>Remember your password? <Link to="/login">Log in</Link></p>
        </div>
      </form>
    </AuthLayout>
  );
};

export default ForgotPasswordPage;