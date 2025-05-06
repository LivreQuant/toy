import React, { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import './AuthLayout.css';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
}

const AuthLayout: React.FC<AuthLayoutProps> = ({ children, title, subtitle }) => {
  return (
    <div className="auth-layout">
      <div className="auth-logo">
        <Link to="/">
          <h1>Trading Platform</h1>
        </Link>
      </div>
      
      <div className="auth-card">
        <div className="auth-header">
          <h2>{title}</h2>
          {subtitle && <p className="auth-subtitle">{subtitle}</p>}
        </div>
        
        <div className="auth-content">
          {children}
        </div>
      </div>
    </div>
  );
};

export default AuthLayout;