import React from 'react';
import { useNavigate } from 'react-router-dom'; // Assuming react-router-dom
import LoginForm from './Auth/LoginForm';
import './LoginPage.css'; // Import styles

const LoginPage: React.FC = () => {
  const navigate = useNavigate();

  const handleLoginSuccess = () => {
    navigate('/home'); // Redirect to home page after successful login
  };

  return (
    <div className="login-page">
        <div className="login-logo">
             <h1>Trading App</h1>
             <p>Please log in to continue</p>
        </div>
      <LoginForm onLoginSuccess={handleLoginSuccess} />
    </div>
  );
};

export default LoginPage;