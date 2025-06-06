// src/components/landing/FeaturesSection.tsx
import React, { forwardRef } from 'react';
import { Box, Container, Typography, Card, CardContent } from '@mui/material';

import { FEATURES_IMAGES } from '@trading-app/assets';

// Assign the specific image paths to your component's variables
const realTimeImage = FEATURES_IMAGES.DASHBOARD;          // 'DASHBOARD' is the key for 'dashboard.png'
const marketImage = FEATURES_IMAGES.MARKET_SIMULATOR;   // 'MARKET_SIMULATOR' is the key for 'market_simulator.jpeg'
const qedImage = FEATURES_IMAGES.QED;                   // 'QED' is the key for 'qed.jpg'
const analyticsImage = FEATURES_IMAGES.ANALYTICS;             // 'ANALYTICS' is the key for 'analytics.jpeg'
const lockImage = FEATURES_IMAGES.LOCK;                 // 'LOCK' is the key for 'lock.jpg'
const apiImage = FEATURES_IMAGES.API;                   // 'API' is the key for 'api.jpeg'

interface FeaturesSectionProps {
  className?: string;
}

const features = [
  {
    title: 'Professional Trading Dashboard',
    description: 'Emulate a professional portfolio manager with our institutional-grade dashboard. Meticulously organize and oversee your portfolio through a sophisticated, hedge fund-level interface.',
    image: realTimeImage
  },
  {
    title: 'Real-Time Market Simulation',
    description: 'Experience an institutional-grade market simulation environment, delivering accurate price dynamics and realistic trade execution, complemented by authentic latency modeling.',
    image: marketImage
  },
  {
    title: 'Provable Track Record',
    description: 'Establish and maintain a cryptographically verifiable and immutable track record of your trading convictions and performance.',
    image: qedImage
  },
  {
    title: 'In Depth Analytics',
    description: 'Leverage detailed analytics dashboards for in-depth P&L tracking, robust attribution analysis, comprehensive risk metrics, and personalized performance factsheets.',
    image: analyticsImage
  },
  {
    title: 'Safeguard Your IP',
    description: 'Safeguard your intellectual property. Our platform operates on processes that do not necessitate access to your strategy details or live trades, ensuring your IP remains confidential.',
    image: lockImage
  },
  {
    title: 'API Integration',
    description: 'Integrate custom trading algorithms effortlessly via our robust and well-documented REST and WebSocket APIs for enhanced automation and control.',
    image: apiImage
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
          Ready to experience being a portfolio manager? Your hedge fund seat awaits.
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