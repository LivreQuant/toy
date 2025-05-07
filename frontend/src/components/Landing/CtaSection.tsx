// src/components/landing/CtaSection.tsx
import React from 'react';
import { Link } from 'react-router-dom';
import { Box, Container, Typography, Button, Grid, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';

const CtaSection: React.FC = () => {
  const theme = useTheme();
  
  return (
    <Box 
      sx={{ 
        py: 10, 
        bgcolor: theme.palette.mode === 'dark' ? 'rgba(0, 0, 0, 0.2)' : 'rgba(0, 0, 0, 0.02)',
        borderTop: 1, 
        borderColor: 'divider'
      }}
    >
      <Container maxWidth="lg">
        <Grid container spacing={6} alignItems="center">
          <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
            <Typography variant="h3" component="h2" gutterBottom>
              Ready to prove your track record?
            </Typography>
            
            <Typography variant="h6" color="textSecondary" paragraph>
              Join our platform today.
            </Typography>
            
            <Button
              component={Link}
              to="/signup"
              variant="contained"
              color="primary"
              size="large"
              sx={{
                py: 1.5,
                px: 4,
                borderRadius: 2,
                fontWeight: 600,
                transition: 'all 0.3s ease',
                border: '2px solid',             // Add border with current color
                borderColor: 'primary.main',     // Set border color to match button color
                '&:hover': {
                  backgroundColor: alpha(theme.palette.background.default, 0.75),
                  borderColor: theme.palette.primary.main,  // Keep border visible on hover
                }
              }}
            >
              Get Started
            </Button>
          </Grid>
          
          <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
            <Box 
              sx={{
                height: 400, 
                bgcolor: 'action.disabled', 
                borderRadius: 3 
              }}
            />
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

export default CtaSection;