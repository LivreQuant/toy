// src/components/landing/TrustedBySection.tsx
import React from 'react';
import { Box, Container, Typography, Grid } from '@mui/material';

const TrustedBySection: React.FC = () => {
  return (
    <Box sx={{ py: 5, bgcolor: 'background.default', borderBottom: 1, borderColor: 'divider' }}>
      <Container maxWidth="lg" sx={{ textAlign: 'center' }}>
        <Typography variant="h6" color="textSecondary" gutterBottom>
          Trusted by top institutions
        </Typography>
        
        <Grid container spacing={4} justifyContent="center" sx={{ mt: 2 }}>
          {[1, 2, 3, 4, 5].map((item) => (
            <Grid {...{component: "div", item: true, key: item} as any}>
              <Box 
                sx={{ 
                  height: 40, 
                  width: 120, 
                  bgcolor: 'action.disabled', 
                  opacity: 0.6,
                  filter: 'grayscale(100%)',
                  transition: 'all 0.3s',
                  '&:hover': {
                    opacity: 1,
                    filter: 'grayscale(0%)',
                  }
                }} 
              />
            </Grid>
          ))}
        </Grid>
      </Container>
    </Box>
  );
};

export default TrustedBySection;