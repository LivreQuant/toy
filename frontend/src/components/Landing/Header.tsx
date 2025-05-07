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
                width: 40, 
                height: 40, 
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
                fontWeight: 'bold'
              }}
            >
              DigitalTrader
            </Typography>
          </Box>
          
          <Box sx={{ display: { xs: 'none', md: 'flex' }, gap: 4 }}>
            <Button color="inherit" href="#features">Features</Button>
            <Button color="inherit" href="#how-it-works">How It Works</Button>
            <Button color="inherit" href="#testimonials">Testimonials</Button>
          </Box>
          
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button 
              component={Link} 
              to="/login" 
              variant="outlined" 
              color="primary"
            >
              Log In
            </Button>
            <Button 
              component={Link} 
              to="/signup" 
              variant="contained" 
              color="primary"
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