// src/components/landing/StatsSection.tsx
import React from 'react';
import { Box, Container, Typography, Grid, Paper, useTheme } from '@mui/material';

const stats = [
  { value: '10M+', label: 'Orders Processed Daily' },
  { value: '$250B+', label: 'Simulated Trading Volume' },
  { value: '5,000+', label: 'Professional Traders' },
  { value: '99.9%', label: 'Platform Uptime' }
];

const StatsSection: React.FC = () => {
  const theme = useTheme();
  
  return (
    <Box 
      sx={{ 
        py: 8,
        background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.primary.light})`,
      }}
    >
      <Container maxWidth="lg">
        <Grid container spacing={3}>
          {stats.map((stat, index) => (
            <Grid {...{component: "div", item: true, xs: 6, md: 3, key: index} as any}>
              <Paper 
                sx={{ 
                  p: 3, 
                  textAlign: 'center',
                  bgcolor: 'rgba(255, 255, 255, 0.1)',
                  backdropFilter: 'blur(5px)',
                  transition: 'transform 0.3s',
                  '&:hover': {
                    transform: 'translateY(-10px)'
                  },
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center'
                }}
              >
                <Typography 
                  variant="h3" 
                  component="div" 
                  sx={{ 
                    fontWeight: 800, 
                    color: 'white',
                    mb: 1
                  }}
                >
                  {stat.value}
                </Typography>
                
                <Typography variant="body1" sx={{ color: 'rgba(255, 255, 255, 0.9)' }}>
                  {stat.label}
                </Typography>
              </Paper>
            </Grid>
          ))}
        </Grid>
      </Container>
    </Box>
  );
};

export default StatsSection;