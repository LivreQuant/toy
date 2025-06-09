// frontend_dist/landing-app/src/components/Landing/Header.tsx
import React from 'react';
import { Box, Container, Typography, Button, Paper, useTheme } from '@mui/material';
import { environmentService } from '../../config';

const Header: React.FC = () => {
  const theme = useTheme();
  
  const handleLogin = () => {
    // Redirect to main app login instead of staying on landing app
    const mainAppUrl = environmentService.getMainAppUrl();
    window.location.href = `${mainAppUrl}/login`;
  };
  
  const handleSignup = () => {
    // Stay on landing app - just navigate to signup route
    window.location.href = '/signup';
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
          
          {/* ONLY MARKETING NAVIGATION - NO APP ROUTES */}
          <Box sx={{ 
            display: { xs: 'none', md: 'flex' }, 
            gap: 4,
            alignItems: 'center'
          }}>
            <Button 
              color="inherit" 
              href="#features"
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
              Features
            </Button>
            <Button 
              color="inherit" 
              href="#how-it-works"
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
              How It Works
            </Button>
            <Button 
              color="inherit" 
              href="#faq"
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
              FAQ
            </Button>
            <Button 
              color="inherit" 
              href="#enterprise"
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
              Enterprise
            </Button>
          </Box>
          
          {/* AUTH BUTTONS - LOGIN GOES TO MAIN APP */}
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