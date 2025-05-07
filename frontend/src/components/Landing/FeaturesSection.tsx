// src/components/landing/FeaturesSection.tsx
import React, { forwardRef } from 'react';
import { Box, Container, Typography, Grid, Card, CardContent } from '@mui/material';

interface FeaturesSectionProps {
  className?: string;
}

const features = [
  {
    title: 'Real-Time Market Simulation',
    description: 'Experience institutional-grade market simulation with accurate price dynamics, order book depth, and latency modeling.'
  },
  {
    title: 'Multiple Trading Books',
    description: 'Create and manage separate trading books for different strategies, asset classes, or risk profiles.'
  },
  {
    title: 'Performance Analytics',
    description: 'Comprehensive analytics dashboards with P&L tracking, risk metrics, and strategy performance indicators.'
  },
  {
    title: 'Advanced Backtesting',
    description: 'Test your strategies against historical data with accurate slippage and transaction cost modeling.'
  },
  {
    title: 'API Integration',
    description: 'Connect your custom trading algorithms via our robust REST and WebSocket APIs.'
  },
  {
    title: 'Compliance Tools',
    description: 'Built-in compliance checks and risk limits to ensure trading strategies meet regulatory requirements.'
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
          Professional Trading Features
        </Typography>
        
        <Typography variant="h6" color="textSecondary" sx={{ mb: 6, maxWidth: 700, mx: 'auto' }}>
          Everything you need to build and test sophisticated trading strategies
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
                  transition: 'all 0.3s',
                  '&:hover': {
                    transform: 'translateY(-10px)',
                    boxShadow: '0 15px 35px rgba(0, 0, 0, 0.1)',
                  }
                }}
              >
                <CardContent sx={{ p: 4, textAlign: 'left' }}>
                  <Box
                    sx={{
                      width: 60,
                      height: 60,
                      borderRadius: 2,
                      bgcolor: 'primary.light',
                      opacity: 0.2,
                      mb: 2,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'primary.main',
                      fontSize: 24
                    }}
                  >
                    {index + 1}
                  </Box>
                  
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