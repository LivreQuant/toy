import React, { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { Box, Typography, Button, } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { config } from '@trading-app/config'; // 🚨 NEW: Import config
import './AuthLayout.css';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
}

const AuthLayout: React.FC<AuthLayoutProps> = ({ children, title, subtitle }) => {
  const navigate = useNavigate();

  // 🚨 NEW: Handle back to landing app
  const handleBackToHome = () => {
    const landingUrl = config.landing.baseUrl;
    console.log(`🔗 Redirecting to landing app: ${landingUrl}`);
    window.location.href = landingUrl;
  };

  return (
    <div className="auth-layout">
      <div className="auth-logo">
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={handleBackToHome} // 🚨 CHANGED: Use new handler
          variant="contained" 
          color="secondary" 
          size="medium"
          sx={{
            py: 1,
            px: 2,
            fontWeight: 600,
            marginBottom: 2,
            borderRadius: 2,
            textTransform: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '48px'
          }}
        >
          Back to Home
        </Button>
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