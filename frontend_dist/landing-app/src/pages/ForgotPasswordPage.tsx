// frontend_dist/landing-app/src/pages/ForgotPasswordPage.tsx (continued)
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import AuthLayout from './AuthLayout';
import { useToast } from '../hooks/useToast';
import { landingApiService } from '../api';
import { environmentService } from '../config/environment';
import './AuthForms.css';

const ForgotPasswordPage: React.FC = () => {
 const [email, setEmail] = useState('');
 const [isSubmitting, setIsSubmitting] = useState(false);
 const [isSubmitted, setIsSubmitted] = useState(false);
 const [apiInitialized, setApiInitialized] = useState(false);
 const [authApiRef, setAuthApiRef] = useState<any>(null);
 const [error, setError] = useState<string | null>(null);
 const { addToast } = useToast();

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
         console.log('🔧 Forgot Password API successfully initialized');
       }
     } catch (error) {
       console.error('❌ API initialization check failed:', error);
       setError('Failed to initialize authentication service. Please refresh the page.');
       addToast('error', 'Authentication service unavailable. Please refresh the page.');
     }
   };
   
   checkApiInitialization();
 }, [addToast]);

 const handleSubmit = async (e: React.FormEvent) => {
   e.preventDefault();
   
   if (!apiInitialized || !authApiRef) {
     setError('Authentication service not ready. Please refresh the page.');
     return;
   }
   
   if (!email.trim() || !/\S+@\S+\.\S+/.test(email)) {
     addToast('warning', 'Please enter a valid email address');
     return;
   }
   
   setIsSubmitting(true);
   setError(null);
   
   try {
     const response = await authApiRef.forgotPassword({ email });
     
     // For security reasons, the API always returns success
     // to avoid revealing if an email exists in the system
     setIsSubmitted(true);
     addToast('success', 'If your email is registered, you will receive a password reset link shortly');
     
     if (environmentService.shouldLog()) {
       console.log('🔧 Forgot password request completed');
     }
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

 // Function to get main app login URL
 const getMainAppLoginUrl = () => {
   const mainAppUrl = environmentService.getMainAppUrl();
   return `${mainAppUrl}/login`;
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

 if (isSubmitted) {
   return (
     <AuthLayout 
       title="Check Your Email" 
       subtitle="If your email is registered, we've sent password reset instructions."
     >
       <div className="auth-success-message">
         <p>Please check your inbox for an email with a link to reset your password.</p>
         <div className="auth-links">
           <a href={getMainAppLoginUrl()} className="auth-button">Return to Login</a>
         </div>
       </div>
     </AuthLayout>
   );
 }

 return (
   <AuthLayout 
     title="Forgot Password" 
     subtitle="Enter your email to receive a password reset link"
   >
     <form className="auth-form" onSubmit={handleSubmit}>
       {error && <div className="form-error">{error}</div>}
       
       <div className="form-group">
         <label htmlFor="email">Email Address</label>
         <input
           id="email"
           type="email"
           value={email}
           onChange={(e) => setEmail(e.target.value)}
           disabled={isSubmitting || !apiInitialized}
           placeholder="Enter your email address"
           required
         />
       </div>
       
       <button 
         type="submit" 
         className="auth-button" 
         disabled={isSubmitting || !apiInitialized}
       >
         {isSubmitting ? 'Submitting...' : 'Reset Password'}
       </button>
       
       <div className="auth-links">
         <p>Forgot your username? <Link to="/forgot-username">Recover username</Link></p>
         <p>Remember your password? <a href={getMainAppLoginUrl()}>Log in</a></p>
       </div>
     </form>
   </AuthLayout>
 );
};

export default ForgotPasswordPage;