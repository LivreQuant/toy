// src/components/landing/TestimonialsSection.tsx
import React, { forwardRef } from 'react';
import { Box, Container, Typography, Paper, Divider } from '@mui/material';

interface TestimonialsSectionProps {
  className?: string;
}

const TestimonialsSection = forwardRef<HTMLDivElement, TestimonialsSectionProps>(({ className }, ref) => {
  return (
    <Box 
      id="testimonials"
      ref={ref}
      className={className}
      sx={{ py: 10 }}
    >
      <Container maxWidth="lg" sx={{ textAlign: 'center' }}>
        <Typography variant="h3" component="h2" gutterBottom>
          What Our Clients Say
        </Typography>
        
        <Box sx={{ maxWidth: 800, mx: 'auto', mt: 6 }}>
          <Paper 
            elevation={3}
            sx={{ 
              p: 5, 
              borderRadius: 3
            }}
          >
            <Typography 
              variant="body1" 
              paragraph 
              sx={{ 
                fontSize: '1.2rem', 
                fontStyle: 'italic', 
                color: 'text.secondary',
                position: 'relative',
                '&::before, &::after': {
                  content: '"""',
                  position: 'absolute',
                  fontSize: '4rem',
                  color: 'rgba(33, 150, 243, 0.1)',
                },
                '&::before': {
                  top: -40,
                  left: -20,
                },
                '&::after': {
                  bottom: -80,
                  right: -20,
                },
                mb: 4
              }}
            >
              "Quantum Trade's simulation environment has been instrumental in refining our algorithmic trading strategies. The accuracy of their market simulation is unparalleled."
            </Typography>
            
            <Divider sx={{ my: 3 }} />
            
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
              <Box 
                sx={{ 
                  width: 60, 
                  height: 60, 
                  borderRadius: '50%', 
                  bgcolor: 'action.disabled'
                }} 
              />
              
              <Box sx={{ textAlign: 'left' }}>
                <Typography variant="h6" component="h4">
                  Sarah Johnson
                </Typography>
                
                <Typography variant="body2" color="textSecondary">
                  Head of Algorithmic Trading, Capital Investments
                </Typography>
              </Box>
            </Box>
          </Paper>
        </Box>
      </Container>
    </Box>
  );
});

export default TestimonialsSection;