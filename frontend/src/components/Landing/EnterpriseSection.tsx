// src/components/Landing/EnterpriseSection.tsx
import React, { forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { Box, Container, Typography, Button, Grid, Card, CardContent, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';

// Use the image you already have access to
import dashboardImage from '../../assets/hero/dashboard.png';

interface EnterpriseSectionProps {
  className?: string;
}

const benefits = [
  {
    title: "Access Verified Talent Pool",
    description: "Connect with portfolio managers who have demonstrable track records verified through our simulation platform.",
    iconText: "🔍" // Using emoji as a fallback
  },
  {
    title: "Data-Driven Allocation Decisions",
    description: "Make allocation decisions based on comprehensive performance metrics and risk analytics, not just interviews and resumes.",
    iconText: "📊"
  },
  {
    title: "Streamline Hiring Process",
    description: "Identify promising candidates who have proven their investment strategies in our realistic market environment.",
    iconText: "🚀"
  }
];

const EnterpriseSection = forwardRef<HTMLDivElement, EnterpriseSectionProps>(({ className }, ref) => {
  const theme = useTheme();
  
  return (
    <Box
      id="enterprise"
      ref={ref}
      className={className}
      sx={{ 
        py: 10,
        background: theme.palette.mode === 'dark' 
          ? 'linear-gradient(160deg, rgba(0, 0, 0, 0.4) 0%, rgba(0, 0, 0, 0.2) 100%)'
          : 'linear-gradient(160deg, #f5f7fa 0%, #e3f2fd 100%)',
      }}
    >
      <Container maxWidth="lg">
        <Box sx={{ textAlign: 'center', mb: 6 }}>
          <Typography 
            variant="h3" 
            component="h2" 
            gutterBottom
            sx={{ 
              fontWeight: 800,
              maxWidth: '800px',
              mx: 'auto'
            }}
          >
            For Institutions & Allocators
          </Typography>
          
          <Typography 
            variant="h6" 
            color="textSecondary" 
            sx={{ 
              maxWidth: '700px',
              mx: 'auto',
              mb: 2
            }}
          >
            Discover proven investment talent for your institution's portfolio
          </Typography>
        </Box>
        
        <Grid container spacing={4} sx={{ mb: 6 }}>
          {benefits.map((benefit, index) => (
            <Grid {...{component: "div", item: true, xs: 12, md: 4, key: index} as any}>
              <Card 
                sx={{ 
                  height: '100%',
                  borderRadius: 3,
                  overflow: 'hidden',
                  transition: 'transform 0.3s, box-shadow 0.3s',
                  '&:hover': {
                    transform: 'translateY(-10px)',
                    boxShadow: '0 15px 35px rgba(0, 0, 0, 0.1)',
                  }
                }}
              >
                {/* Using a gradient background with an emoji icon instead of image */}
                <Box
                  sx={{
                    height: 180,
                    width: '100%',
                    background: index === 0 
                      ? 'linear-gradient(135deg, #0288d1 0%, #01579b 100%)'
                      : index === 1
                        ? 'linear-gradient(135deg, #0097a7 0%, #006064 100%)'
                        : 'linear-gradient(135deg, #00897b 0%, #004d40 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Typography variant="h1" sx={{ color: 'white' }}>
                    {benefit.iconText}
                  </Typography>
                </Box>
                <CardContent sx={{ p: 4 }}>
                  <Typography variant="h5" component="h3" gutterBottom sx={{ fontWeight: 600 }}>
                    {benefit.title}
                  </Typography>
                  <Typography variant="body1" color="textSecondary">
                    {benefit.description}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
        
        {/* Adding a more substantial CTA section */}
        <Box 
          sx={{ 
            textAlign: 'center',
            py: 5,
            px: { xs: 2, md: 8 },
            borderRadius: 4,
            bgcolor: theme.palette.mode === 'dark' 
              ? alpha(theme.palette.primary.main, 0.15)
              : alpha(theme.palette.primary.main, 0.05),
            border: `1px solid ${alpha(theme.palette.primary.main, 0.1)}`,
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.05)',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {/* Background decoration */}
          <Box
            sx={{
              position: 'absolute',
              top: -100,
              right: -100,
              width: 300,
              height: 300,
              borderRadius: '50%',
              background: alpha(theme.palette.primary.main, 0.1),
              zIndex: 0
            }}
          />
          
          <Box sx={{ position: 'relative', zIndex: 1 }}>
            <Typography variant="h4" gutterBottom fontWeight="600">
              Looking for Proven Investment Talent?
            </Typography>
            
            <Typography variant="body1" paragraph sx={{ maxWidth: '800px', mx: 'auto', mb: 4 }}>
              Whether you're an endowment, pension fund, fund-of-funds, or investment committee, 
              our platform helps you identify and evaluate portfolio managers with verified track
              records in our realistic market environment. Access our growing database of skilled 
              investors with transparent performance metrics.
            </Typography>
            
            <Grid container spacing={3} justifyContent="center" sx={{ mt: 3 }}>
              <Grid {...{component: "div", item: true, xs: 12, sm: 6, md: 4} as any}>
                <Box sx={{ 
                  p: 2, 
                  textAlign: 'center',
                  borderRadius: 2,
                  bgcolor: alpha(theme.palette.primary.main, 0.07)
                }}>
                  <Typography variant="h5" component="div" sx={{ fontWeight: 700, mb: 1 }}>
                    Transparent
                  </Typography>
                  <Typography variant="body2">
                    Access verified trading history and performance metrics
                  </Typography>
                </Box>
              </Grid>
              
              <Grid {...{component: "div", item: true, xs: 12, sm: 6, md: 4} as any}>
                <Box sx={{ 
                  p: 2, 
                  textAlign: 'center',
                  borderRadius: 2,
                  bgcolor: alpha(theme.palette.primary.main, 0.07)
                }}>
                  <Typography variant="h5" component="div" sx={{ fontWeight: 700, mb: 1 }}>
                    Reliable
                  </Typography>
                  <Typography variant="body2">
                    Performance data validated through our simulation platform
                  </Typography>
                </Box>
              </Grid>
              
              <Grid {...{component: "div", item: true, xs: 12, sm: 6, md: 4} as any}>
                <Box sx={{ 
                  p: 2, 
                  textAlign: 'center',
                  borderRadius: 2,
                  bgcolor: alpha(theme.palette.primary.main, 0.07)
                }}>
                  <Typography variant="h5" component="div" sx={{ fontWeight: 700, mb: 1 }}>
                    Diverse
                  </Typography>
                  <Typography variant="body2">
                    Find talent across various strategies and investment styles
                  </Typography>
                </Box>
              </Grid>
            </Grid>
            
            <Button 
              variant="contained" 
              color="primary"
              size="large"
              component={Link}
              to="/enterprise-contact"
              sx={{
                py: 1.8,
                px: 6,
                mt: 6,
                borderRadius: 2,
                fontWeight: 600,
                fontSize: '1.1rem',
                boxShadow: '0 8px 20px rgba(33, 150, 243, 0.3)',
                transition: 'all 0.3s ease',
                '&:hover': {
                  transform: 'translateY(-5px)',
                  boxShadow: '0 12px 25px rgba(33, 150, 243, 0.4)',
                }
              }}
            >
              Schedule a Consultation
            </Button>
          </Box>
        </Box>
      </Container>
    </Box>
  );
});

export default EnterpriseSection;