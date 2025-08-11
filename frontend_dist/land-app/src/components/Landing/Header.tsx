// frontend_dist/landing-app/src/components/Landing/Header.tsx
import React from 'react';
import { Box, Container, Typography, Button, Paper, useTheme } from '@mui/material';
import { environmentService } from '../../config';

const Header: React.FC = () => {
  const theme = useTheme();
  
  const handleLogin = () => {
    // Debug what's actually loaded
    console.log('🔍 DEBUG Environment Variables:');
    console.log('REACT_APP_MAIN_URL:', process.env.REACT_APP_MAIN_URL);
    console.log('REACT_APP_LAND_URL:', process.env.REACT_APP_LAND_URL);
    console.log('REACT_APP_GATEWAY_URL:', process.env.REACT_APP_GATEWAY_URL);
    console.log('REACT_APP_TYPE:', process.env.REACT_APP_TYPE);
    console.log('NODE_ENV:', process.env.NODE_ENV);
    
    console.log('🔍 DEBUG environmentService:');
    console.log('getGatewayUrl():', environmentService.getGatewayUrl());
    console.log('config:', environmentService.getConfig());
    
    const loginUrl12 = environmentService.getLoginUrl();
    console.log('🔗 Final loginUrl:', loginUrl12);

    // Now points to /app/login instead of /home/login
    const loginUrl = `${environmentService.getGatewayUrl()}/app/login`;
    
    if (environmentService.shouldLog()) {
      console.log('🔗 HEADER: Redirecting to login:', loginUrl);
    }
    
    window.location.href = loginUrl;
  };
  
  const handleSignup = () => {
    const signupUrl = environmentService.getSignupUrl();
    window.location.href = signupUrl;
  };
  
  return (
    <Paper 
      elevation={1}
      sx={{ 
        position: 'sticky', 
        top: 0, 
        zIndex: 100,
        borderRadius: 0,
        py: 2
      }}
    >
      <Container maxWidth="lg">
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Box 
              sx={{ 
                width: 30, 
                height: 30, 
                bgcolor: 'primary.main', 
                borderRadius: 2,
                mr: 2
              }} 
            />
            <Typography 
              variant="h4" 
              component="h1" 
              sx={{ 
                background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.primary.light})`,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                fontWeight: 'bold',
                margin: 0,
                padding: 0,
                paddingTop: 1,
                lineHeight: 1
              }}
            >
              DigitalTrader
            </Typography>
          </Box>
          
          {/* MARKETING NAVIGATION */}
          <Box sx={{ 
            display: { xs: 'none', md: 'flex' }, 
            gap: 4,
            alignItems: 'center'
          }}>
            {['features', 'how-it-works', 'faq', 'enterprise'].map((section) => (
              <Button 
                key={section}
                color="inherit" 
                href={`#${section}`}
                sx={{
                  padding: "8px 16px",
                  margin: 0,
                  minHeight: 0,
                  lineHeight: 1,
                  borderRadius: 0,
                  textTransform: 'none',
                  position: 'relative',
                  '&::after': {
                    content: '""',
                    position: 'absolute',
                    bottom: 0,
                    left: 0,
                    width: 0,
                    height: '2px',
                    backgroundColor: 'primary.main',
                    transition: 'width 0.3s ease'
                  },
                  '&:hover': {
                    boxShadow: 'none',
                    backgroundColor: 'transparent',
                    '&::after': {
                      width: '100%'
                    }
                  }
                }}
              >
                {section.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </Button>
            ))}
          </Box>
          
          {/* AUTH BUTTONS */}
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button 
              onClick={handleLogin}
              variant="outlined" 
              color="primary"
              sx={{
                borderRadius: 1,
                padding: '8px 16px',
                fontWeight: 500,
                textTransform: 'none',
                '&:hover': {
                  backgroundColor: 'rgba(33, 150, 243, 0.08)',
                  transform: 'none'
                }
              }}
            >
              Log In
            </Button>
            <Button 
              onClick={handleSignup}
              variant="contained" 
              color="primary"
              sx={{
                borderRadius: 1,
                padding: '8px 16px',
                fontWeight: 500,
                textTransform: 'none',
                boxShadow: 'none',
                border: '2px solid',
                borderColor: theme.palette.primary.main,
                '&:hover': {
                  border: '2px solid',
                  borderColor: theme.palette.primary.main,
                  backgroundColor: theme.palette.background.default,
                  boxShadow: '0 4px 8px rgba(33, 150, 243, 0.25)',
                  transform: 'none',
                }
              }}
            >
              Get Started
            </Button>
          </Box>
        </Box>
      </Container>
    </Paper>
  );
};

export default Header;