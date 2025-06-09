import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AuthLayout from './AuthLayout';
import { useToast } from '../hooks/useToast';
import { getAuthApi } from '../api';
import { environmentService } from '../config/environment';
import './AuthForms.css';

const SignupPage: React.FC = () => {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiInitialized, setApiInitialized] = useState(false);
  const [authApiRef, setAuthApiRef] = useState<any>(null);
  const navigate = useNavigate();
  const { addToast } = useToast();

  // Check API initialization on component mount
  useEffect(() => {
    const checkApiInitialization = async () => {
      try {
        const authApi = await getAuthApi();
        
        if (!authApi || typeof authApi.signup !== 'function') {
          throw new Error('Auth API missing required methods');
        }
        
        setAuthApiRef(authApi);
        setApiInitialized(true);
        
        if (environmentService.shouldLog()) {
          console.log('🔧 Signup API successfully initialized');
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

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    
    // Clear specific error when field is edited
    if (errors[name]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[name];
        return newErrors;
      });
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    
    // Username validation
    if (!formData.username.trim()) {
      newErrors.username = 'Username is required';
    } else if (formData.username.length < 3) {
      newErrors.username = 'Username must be at least 3 characters';
    }
    
    // Email validation
    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Email address is invalid';
    }
    
    // Password validation
    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    } else if (!/[A-Z]/.test(formData.password)) {
      newErrors.password = 'Password must contain at least one uppercase letter';
    } else if (!/[a-z]/.test(formData.password)) {
      newErrors.password = 'Password must contain at least one lowercase letter';
    } else if (!/[0-9]/.test(formData.password)) {
      newErrors.password = 'Password must contain at least one number';
    } else if (!/[!@#$%^&*(),.?":{}|<>]/.test(formData.password)) {
      newErrors.password = 'Password must contain at least one special character';
    }
    
    // Confirm password validation
    if (formData.password !== formData.confirmPassword) {
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
    
    if (!validateForm()) {
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const response = await authApiRef.signup({
        username: formData.username,
        email: formData.email,
        password: formData.password
      });
      
      if (response.success) {
        addToast('success', 'Account created successfully! Please check your email to verify your account.');
        
        // Navigate to verify-email with both state and URL parameters
        navigate(`/verify-email?userId=${response.userId}&email=${encodeURIComponent(formData.email)}`, { 
          state: { 
            userId: response.userId,
            email: formData.email 
          } 
        });
      } else {
        // API returned success: false
        setErrors({ 
          form: response.error || 'An error occurred during signup. Please try again.' 
        });
        addToast('error', response.error || 'Failed to create account');
      }
    } catch (error: any) {
      if (environmentService.shouldLog()) {
        console.error('Signup error:', error);
      }
      setErrors({ 
        form: error.message || 'An error occurred during signup. Please try again.' 
      });
      addToast('error', error.message || 'Error creating account');
    } finally {
      setIsSubmitting(false);
    }
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

  return (
    <AuthLayout 
      title="Create an Account" 
      subtitle="Join DigitalTrader to get started"
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        {errors.form && <div className="form-error">{errors.form}</div>}
        
        <div className="form-group">
          <label htmlFor="username">Username</label>
          <input
            id="username"
            type="text"
            name="username"
            value={formData.username}
            onChange={handleChange}
            disabled={isSubmitting || !apiInitialized}
            placeholder="Choose a username"
            className={errors.username ? 'error' : ''}
          />
          {errors.username && <div className="field-error">{errors.username}</div>}
        </div>
        
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            name="email"
            value={formData.email}
            onChange={handleChange}
            disabled={isSubmitting || !apiInitialized}
            placeholder="Your email address"
            className={errors.email ? 'error' : ''}
          />
          {errors.email && <div className="field-error">{errors.email}</div>}
        </div>
        
        <div className="form-group">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            name="password"
            value={formData.password}
            onChange={handleChange}
            disabled={isSubmitting || !apiInitialized}
            placeholder="Create a secure password"
            className={errors.password ? 'error' : ''}
          />
          {errors.password && <div className="field-error">{errors.password}</div>}
        </div>
        
        <div className="form-group">
          <label htmlFor="confirmPassword">Confirm Password</label>
          <input
            id="confirmPassword"
            type="password"
            name="confirmPassword"
            value={formData.confirmPassword}
            onChange={handleChange}
            disabled={isSubmitting || !apiInitialized}
            placeholder="Confirm your password"
            className={errors.confirmPassword ? 'error' : ''}
          />
          {errors.confirmPassword && <div className="field-error">{errors.confirmPassword}</div>}
        </div>
        
        <button 
          type="submit" 
          className="auth-button" 
          disabled={isSubmitting || !apiInitialized}
        >
          {isSubmitting ? 'Creating Account...' : 'Create Account'}
        </button>
        
        <div className="auth-links">
          <p>Already have an account? <Link to="/login">Log in</Link></p>
        </div>
      </form>
    </AuthLayout>
  );
};

export default SignupPage;