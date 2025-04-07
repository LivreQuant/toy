import React from 'react';
import Login from '../components/Auth/Login';
import './LoginPage.css';

const LoginPage: React.FC = () => {
  return (
    <div className="login-page">
      <div className="login-logo">
        <h1>Trading Simulator</h1>
        <p>Professional-grade simulation platform</p>
      </div>
      <Login />
    </div>
  );
};

export default LoginPage;