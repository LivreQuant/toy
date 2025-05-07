import React, { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { Box, Typography, Button, } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import './AuthLayout.css';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
}

const AuthLayout: React.FC<AuthLayoutProps> = ({ children, title, subtitle }) => {
  const navigate = useNavigate();

  return (
    <div className="auth-layout">
      
      <div className="auth-card">
        <div className="auth-header">
          <h2>{title}</h2>
          {subtitle && <p className="auth-subtitle">{subtitle}</p>}
        </div>
        <div className="auth-content">
          {children}
        </div>
      </div>

      <div className="auth-logo">
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/')}
          variant="contained" 
          color="secondary" 
          size="medium"
          sx={{
            py: 1,         // Increased vertical padding
            px: 2,           // Increased horizontal padding
            fontWeight: 600,
            marginTop: 2,
            borderRadius: 2,
            textTransform: 'none',
            display: 'flex',  // Added display flex
            alignItems: 'center', // Added to center text vertically
            justifyContent: 'center', // Added to center text horizontally
            height: '48px'    // Set a fixed height
          }}
        >
          Back to Home
        </Button>
      </div>

    </div>
  );
};

export default AuthLayout;