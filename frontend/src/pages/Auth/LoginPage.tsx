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
    
    console.log("🔍 LOGIN: Submit button clicked");
    
    if (!username.trim() || !password) {
      setError('Please enter both username and password');
      console.log("🔍 LOGIN: Missing username or password");
      return;
    }
    
    setError(null);
    setIsSubmitting(true);
    console.log("🔍 LOGIN: Starting login process for user:", username);
    
    try {
      console.log("🔍 LOGIN: Calling login API");
      const response = await login({ 
        username, 
        password,
      });
      
      console.log("🔍 LOGIN: Got response from login API:", JSON.stringify(response));
      
      // Check for verification required case
      if (response.requiresVerification && response.userId) {
        console.log("🔍 LOGIN: Email verification required, userId:", response.userId);
        
        // Create an object with verified properties
        const verificationState = { 
          userId: response.userId,
          needsVerification: true
        };
        
        // Add email if it exists in the response
        if ('email' in response) {
          // This approach avoids TypeScript errors by using dynamic property access
          (verificationState as any).email = response.email;
        }
        
        console.log("🔍 LOGIN: Navigating to verification page");
        navigate(`/verify-email?userId=${response.userId}`, {
          state: verificationState
        });
        
        addToast('warning', 'Please verify your email address before logging in.');
        return;
      }
      
      if (response.success) {
        console.log("🔍 LOGIN: Login successful, redirecting");
        const state = location.state as LocationState;
        const redirectTo = state?.from || '/home';
        navigate(redirectTo);
      } else {
        console.log("🔍 LOGIN: Login failed:", response.error);
        setError(response.error || 'Invalid username or password');
      }
    } catch (error: any) {
      console.error("🔍 LOGIN: Exception during login:", error);
      setError(error.message || 'Login failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout 
      title="Log In" 
      subtitle="Welcome back to the DigitalTrader"
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
          <p>Forgot your password? <Link to="/forgot-password">Reset password</Link></p>
        </div>
      </form>
    </AuthLayout>
  );
};

export default LoginPage;