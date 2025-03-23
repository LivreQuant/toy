import React from 'react';
import Login from '../components/Auth/Login';

const LoginPage: React.FC = () => {
  return (
    <div className="login-page">
      <div className="login-logo">
        <h1>Trading Simulator</h1>
        <p>Professional-grade simulation platform</p>
      </div>
      <Login />
      <style jsx>{`
        .login-page {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          background-color: #f5f7fa;
          padding: 20px;
        }
        
        .login-logo {
          text-align: center;
          margin-bottom: 30px;
        }
        
        .login-logo h1 {
          margin-bottom: 10px;
          color: #333;
        }
        
        .login-logo p {
          color: #666;
        }
      `}</style>
    </div>
  );
};

export default LoginPage;