// src/pages/Auth/LoginPage.tsx
import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useToast } from '../../hooks/useToast';
import AuthLayout from './AuthLayout';
import './AuthForms.css';

interface LocationState {
  verified?: boolean;
  from?: string;
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
    
    try {
      const success = await login({ 
        username, 
        password,
        rememberMe
      });
      
      if (success) {
        const state = location.state as LocationState;
        const redirectTo = state?.from || '/home';
        navigate(redirectTo);
      } else {
        setError('Invalid username or password');
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