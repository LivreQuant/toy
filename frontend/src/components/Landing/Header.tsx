import React from 'react';
import { Link } from 'react-router-dom';
import { Box, Container, Typography, Button, Paper, useTheme } from '@mui/material';

// Define the component
const Header: React.FC = () => {
  const theme = useTheme();
  
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
                margin: 0,      // Set all margins to 0
                padding: 0,     // Set all padding to 0
                paddingTop: 1,
                lineHeight: 1   // Adjust line height to be tighter
              }}
            >
              DigitalTrader
            </Typography>
          </Box>
          
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
                borderRadius: 0, // Remove border radius
                textTransform: 'none',
                position: 'relative', // For the underline positioning
                '&::after': {
                  content: '""',
                  position: 'absolute',
                  bottom: 0,
                  left: 0,
                  width: 0, // Start with 0 width
                  height: '2px',
                  backgroundColor: 'primary.main',
                  transition: 'width 0.3s ease'
                },
                '&:hover': {
                  boxShadow: 'none',
                  backgroundColor: 'transparent', // Remove background hover
                  '&::after': {
                    width: '100%' // Expand to full width on hover
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
          
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button 
              component={Link} 
              to="/login" 
              variant="outlined" 
              color="primary"
              sx={{
                borderRadius: 1,
                padding: '8px 16px',
                fontWeight: 500,
                textTransform: 'none',
                // No transform hover effect
                '&:hover': {
                  backgroundColor: 'rgba(33, 150, 243, 0.08)', // Subtle background change on hover
                  transform: 'none' // Remove any transform animation
                }
              }}
            >
              Log In
            </Button>
            <Button 
              component={Link} 
              to="/signup" 
              variant="contained" 
              color="primary"
              sx={{
                borderRadius: 1,
                padding: '8px 16px',
                fontWeight: 500,
                textTransform: 'none',
                boxShadow: 'none',
                '&:hover': {
                  backgroundColor: theme.palette.background.default,
                  boxShadow: '0 4px 8px rgba(33, 150, 243, 0.25)', // Blue shadow with offset and blur
                  transform: 'none', // Remove any transform animation
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