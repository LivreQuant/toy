// src/pages/Auth/LoginPage.tsx
import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useToast } from '../../hooks/useToast';
import AuthLayout from './AuthLayout';
import './AuthForms.css';

// Define the location state interface
interface LocationState {
  verified?: boolean;
  from?: string;
  userId?: string | number;
  needsVerification?: boolean;
}

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const { login, isAuthenticated } = useAuth();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  
  // Check for redirect state
  useEffect(() => {
    const state = location.state as LocationState;
    
    if (state?.verified) {
      addToast('success', 'Email verified successfully! You can now log in.');
    }
  }, [location, addToast]);
  
  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/home');
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!username.trim() || !password) {
      setError('Please enter both username and password');
      return;
    }
    
    setError(null);
    setIsSubmitting(true);
    
    // Extract location state correctly with type safety
    const locationState = location.state as LocationState;
    
    try {
      const response = await login({ 
        username, 
        password,
        rememberMe
      });
      
      if (response.success) {
        // Successful login, redirect to home
        const redirectTo = locationState?.from || '/home';
        navigate(redirectTo);
      } else if (response.requiresVerification && response.userId) {
        // Email needs verification, redirect to verification page
        navigate(`/verify-email?userId=${response.userId}`, {
          state: { 
            userId: response.userId,
            needsVerification: true
          }
        });
        addToast('warning', 'Please verify your email address before logging in.');
      } else {
        // General login failure
        setError(response.error || 'Invalid username or password');
      }
    } catch (error: any) {
      setError(error.message || 'Login failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout 
      title="Log In" 
      subtitle="Welcome back to the Trading Platform"
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
            disabled={isSubmitting}
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
            disabled={isSubmitting}
            placeholder="Enter your password"
          />
        </div>
        
        <div className="form-options">
          <div className="remember-me">
            <input
              id="rememberMe"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              disabled={isSubmitting}
            />
            <label htmlFor="rememberMe">Remember me</label>
          </div>
          <Link to="/forgot-password" className="forgot-link">Forgot password?</Link>
        </div>
        
        <button 
          type="submit" 
          className="auth-button" 
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Logging in...' : 'Log In'}
        </button>
        
        <div className="auth-links">
          <p>Don't have an account? <Link to="/signup">Sign up</Link></p>
          <p>Forgot your username? <Link to="/forgot-username">Recover username</Link></p>
        </div>
      </form>
    </AuthLayout>
  );
};

export default LoginPage;