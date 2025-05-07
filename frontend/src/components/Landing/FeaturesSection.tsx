// src/components/landing/FeaturesSection.tsx
import React, { forwardRef } from 'react';
import { Box, Container, Typography, Grid, Card, CardContent } from '@mui/material';

// Import your images
// For example:
import realTimeImage from '../../assets/features/dashboard.png';

interface FeaturesSectionProps {
  className?: string;
}

const features = [
  {
    title: 'Professional Trading Dashboard',
    description: 'Create and manage separate trading books for different strategies, asset classes, or risk profiles.',
    image: realTimeImage
  },
  {
    title: 'Real-Time Market Simulation',
    description: 'Experience institutional-grade market simulation with accurate price dynamics, order book depth, and latency modeling.',
    image: realTimeImage
  },
  {
    title: 'Provable Track Record',
    description: 'Test your strategies against historical data with accurate slippage and transaction cost modeling.',
    image: realTimeImage
  },
  {
    title: 'In Depth Analytics',
    description: 'Comprehensive analytics dashboards with P&L tracking, risk metrics, and strategy performance indicators.',
    image: realTimeImage
  },
  {
    title: 'Protect Your IP',
    description: 'Built-in compliance checks and risk limits to ensure trading strategies meet regulatory requirements.',
    image: realTimeImage
  },
  {
    title: 'API Integration',
    description: 'Connect your custom trading algorithms via our robust REST and WebSocket APIs.',
    image: realTimeImage
  }
];

const FeaturesSection = forwardRef<HTMLDivElement, FeaturesSectionProps>(({ className }, ref) => {
  return (
    <Box
      id="features"
      ref={ref}
      className={className}
      sx={{ py: 10 }}
    >
      <Container maxWidth="lg" sx={{ textAlign: 'center' }}>
        <Typography variant="h3" component="h2" gutterBottom>
          The Fund Simulator
        </Typography>
        
        <Typography variant="h6" color="textSecondary" sx={{ mb: 6, maxWidth: 700, mx: 'auto' }}>
          Everything you need to demonstrate your investment aptitude
        </Typography>
        
        <Box sx={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 4 }}>
          {features.map((feature, index) => (
            <Box 
              key={index}
              sx={{ 
                width: '45%', 
                mb: 4
              }}
            >
              <Card
                sx={{
                  height: '100%',
                  borderRadius: 3,
                  overflow: 'hidden', // Important for containing the image
                  transition: 'all 0.3s',
                  '&:hover': {
                    transform: 'translateY(-10px)',
                    boxShadow: '0 15px 35px rgba(0, 0, 0, 0.1)',
                  }
                }}
              >
                {/* Image at the top of the card */}
                <Box
                  sx={{
                    height: 160, // Set a fixed height for the image section
                    width: '100%',
                    backgroundImage: `url(${feature.image})`,
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                  }}
                />
                
                <CardContent sx={{ p: 4, textAlign: 'left' }}>                  
                  <Typography variant="h5" component="h3" gutterBottom sx={{ fontWeight: 600 }}>
                    {feature.title}
                  </Typography>
                  
                  <Typography variant="body1" color="textSecondary">
                    {feature.description}
                  </Typography>
                </CardContent>
              </Card>
            </Box>
          ))}
        </Box>
      </Container>
    </Box>
  );
});

export default FeaturesSection;