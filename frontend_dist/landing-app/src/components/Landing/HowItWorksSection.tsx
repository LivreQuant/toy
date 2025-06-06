// src/components/landing/HowItWorksSection.tsx
import React from 'react';
import { Box, Container, Typography, useTheme, useMediaQuery } from '@mui/material';

import { HOW_IT_WORKS_IMAGES } from '@trading-app/assets';

// Assign the specific image paths to your component's variables
const strategyImage = HOW_IT_WORKS_IMAGES.STRATEGY;     // 'STRATEGY' is the key for 'strategy.jpeg'
const blockchainImage = HOW_IT_WORKS_IMAGES.BLOCKCHAIN;   // 'BLOCKCHAIN' is the key for 'blockchain.jpeg'
const tradesImage = HOW_IT_WORKS_IMAGES.TRADES;       // 'TRADES' is the key for 'trades.png'
const factsheetImage = HOW_IT_WORKS_IMAGES.FACTSHEET;   // 'FACTSHEET' is the key for 'factsheet.jpg'

const steps = [
  {
    step: 1,
    title: 'Generate & Encrypt Convictions',
    description: 'Develop your trading strategies and generate market convictions on your personal and secured device. Your convictions are encrypted with your unique key, securing your intellectual property from the moment it you generated them.',
    image: strategyImage
  },
  {
    step: 2,
    title: 'Commit to Public Blockchain',
    description: 'Upload your encrypted convictions and we will securely commit them to a public blockchain. This creates an immutable and independently verifiable record of their existence and precise origination time.',
    image: blockchainImage
  },
  {
    step: 3,
    title: 'Selective Disclosure & Verification',
    description: 'Reveal your original unencrypted convictions at your chosen time, under your complete control. This platform performs verificaties them against the blockchain record, confirming authenticity and timestamp integrity.',
    image: tradesImage
  },
  {
    step: 4,
    title: 'Generate Provable Track Record',
    description: 'Upon verification, our simulation engine processes your authentically time-stamped convictions. This generates a comprehensive, provable performance record and detailed portfolio factsheets that validate your investment aptitude.',
    image: factsheetImage
  }
];

const HowItWorksSection: React.FC = () => {
  const theme = useTheme();
  const isLgUp = useMediaQuery(theme.breakpoints.up('lg'));
  const isMdUp = useMediaQuery(theme.breakpoints.up('md'));
  const isSmUp = useMediaQuery(theme.breakpoints.up('sm'));
  
  // Set the appropriate layout based on screen size
  const getStepWidth = () => {
    if (isLgUp) return 'calc(25% - 24px)'; // For large screens, 4 items per row with gap
    if (isMdUp) return 'calc(50% - 16px)';  // For medium screens, 2 items per row
    if (isSmUp) return 'calc(50% - 16px)';  // For small screens, 2 items per row
    return '100%';                          // For extra small screens, 1 item per row
  };
  
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
        
        <Box sx={{ 
          display: 'flex', 
          flexWrap: { xs: 'wrap', lg: 'nowrap' }, 
          justifyContent: 'center', 
          gap: { xs: 2, md: 3 } 
        }}>
          {steps.map((step) => (
            <Box 
              key={step.step}
              sx={{ 
                width: getStepWidth(),
                mb: { xs: 4, lg: 0 },
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
              
              <Typography variant="h5" component="h3" gutterBottom sx={{ fontWeight: 600, marginBottom: 4 }}>
                {step.title}
              </Typography>
              
              <Typography variant="body1" color="textSecondary" paragraph sx={{
                // Make text smaller on smaller screens
                fontSize: { xs: '0.875rem', md: '1rem' },
                // Set a consistent height for text containers
                height: { lg: '130px' },
                display: 'flex',
                alignItems: 'center',
                marginBottom: 4
              }}>
                {step.description}
              </Typography>
              
              <Box 
                sx={{ 
                  mt: 'auto',
                  width: '100%',
                  height: { xs: 160, md: 200 },
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