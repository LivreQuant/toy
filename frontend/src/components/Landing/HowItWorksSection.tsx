// src/components/landing/HowItWorksSection.tsx
import React from 'react';
import { Box, Container, Typography, useTheme } from '@mui/material';

// Import your images
// For example:
import trackPortfolioImage from '../../assets/howItWorks/dashboard.png';

const steps = [
  {
    step: 1,
    title: 'Track Your Portfolio',
    description: 'Configure your trading book with custom parameters, capital allocation, and risk limits.',
    image: trackPortfolioImage
  },
  {
    step: 2,
    title: 'Trusted Timestamps',
    description: 'Build and refine your trading strategies using our intuitive interface or API integration.',
    image: trackPortfolioImage
  },
  {
    step: 3,
    title: 'Simulate & Analyze',
    description: 'Run your strategies in our realistic market environment and analyze performance in real-time.',
    image: trackPortfolioImage
  }
];

const HowItWorksSection: React.FC = () => {
  const theme = useTheme();
  
  return (
    <Box 
      id="how-it-works"
      sx={{ 
        py: 10, 
        bgcolor: theme.palette.mode === 'dark' ? 'rgba(0, 0, 0, 0.2)' : 'rgba(0, 0, 0, 0.02)'
      }}
    >
      <Container maxWidth="lg" sx={{ textAlign: 'center' }}>
        <Typography variant="h3" component="h2" gutterBottom>
          How It Works
        </Typography>
        
        <Typography variant="h6" color="textSecondary" sx={{ mb: 6 }}>
          Start creating your provable track record today
        </Typography>
        
        <Box sx={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 4 }}>
          {steps.map((step) => (
            <Box 
              key={step.step}
              sx={{ 
                width: '30%', 
                mb: 4,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center'
              }}
            >
              <Box 
                sx={{ 
                  width: 50,
                  height: 50,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.primary.light})`,
                  color: 'white',
                  fontWeight: 'bold',
                  fontSize: '1.5rem',
                  mb: 2
                }}
              >
                {step.step}
              </Box>
              
              <Typography variant="h5" component="h3" gutterBottom sx={{ fontWeight: 600 }}>
                {step.title}
              </Typography>
              
              <Typography variant="body1" color="textSecondary" paragraph>
                {step.description}
              </Typography>
              
              {/* Replace the empty box with an actual image */}
              <Box 
                sx={{ 
                  mt: 'auto',
                  width: '100%',
                  height: 200,
                  bgcolor: 'background.paper',
                  borderRadius: 2,
                  boxShadow: '0 10px 30px rgba(0, 0, 0, 0.08)',
                  backgroundImage: `url(${step.image})`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center',
                }}
              />
            </Box>
          ))}
        </Box>
      </Container>
    </Box>
  );
};

export default HowItWorksSection;