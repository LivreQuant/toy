// src/components/Landing/EnterpriseSection.tsx
import React, { forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { Box, Container, Typography, Button, Grid, Card, CardContent, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';

// Import images for each benefit card
// You'll need to create these images or use from your assets
import accessTalentImage from '../../assets/enterprise/candidate.png';
import moneyballImage from '../../assets/enterprise/moneyball.jpg';
import needleImage from '../../assets/enterprise/needle.jpeg';
import dueDiligenceImage from '../../assets/enterprise/vet.jpg';

interface EnterpriseSectionProps {
  className?: string;
}

const benefits = [
  {
    title: "Access Verified Talent Pool",
    description: "Connect with portfolio managers who have demonstrable track records verified through our simulation platform.",
    image: accessTalentImage
  },
  {
    title: "Data-Driven Decisions",
    description: "Make decisions based on comprehensive performance metrics and risk analytics, not just endless exhaustive interviews.",
    image: moneyballImage
  },
  {
    title: "Detailed Search Criteria",
    description: "Identify individuals and funds that best satisfy your requirements and constraints.",
    image: needleImage
  },
  {
    title: "Outsource Your Due Diligence",
    description: "Let us handle the complex vetting process for your investment candidates with our rigorous evaluation framework and blockchain-verified performance data.",
    image: dueDiligenceImage
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
            Enterprise Solutions
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
            Discover proven investment talent for your institution's team or portfolio
          </Typography>
        </Box>
        
        {/* Benefits cards layout */}
        <Box sx={{ 
          display: 'flex', 
          flexWrap: 'wrap', 
          justifyContent: 'center', 
          gap: { xs: 2, md: 4 } 
        }}>
          {benefits.map((benefit, index) => (
            <Box 
              key={index}
              sx={{ 
                width: { xs: '100%', sm: '45%' }, 
                mb: 4
              }}
            >
              <Card
                sx={{
                  height: '100%',
                  borderRadius: 3,
                  overflow: 'hidden',
                  transition: 'all 0.3s',
                  '&:hover': {
                    transform: 'translateY(-10px)',
                    boxShadow: '0 15px 35px rgba(0, 0, 0, 0.1)',
                  }
                }}
              >
                {/* Image section instead of gradient background with emoji */}
                <Box
                  sx={{
                    height: 200,
                    width: '100%',
                    position: 'relative',
                    overflow: 'hidden'
                  }}
                >
                  <Box
                    component="img"
                    src={benefit.image}
                    alt={benefit.title}
                    sx={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                      transition: 'transform 0.6s ease',
                      '&:hover': {
                        transform: 'scale(1.1)',
                      }
                    }}
                  />
                  
                  {/* Optional overlay to ensure text readability */}
                  <Box
                    sx={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      height: '100%',
                      background: 'linear-gradient(to top, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.2) 50%, rgba(0,0,0,0) 100%)',
                      display: 'flex',
                      alignItems: 'flex-end',
                      p: 2
                    }}
                  >
                  </Box>
                </Box>
                
                <CardContent sx={{ p: 3 }}>
                  <Typography 
                    variant="h5" 
                    component="h3" 
                  >
                    {benefit.title}
                  </Typography>
                  <Typography variant="body1" color="textSecondary">
                    {benefit.description}
                  </Typography>
                </CardContent>
              </Card>
            </Box>
          ))}
        </Box>
        
        {/* CTA section remains unchanged */}
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
            mt: 4  // Added margin-top for spacing from the cards
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
              investors with transparent and auditable performance metrics.
            </Typography>
            
            <Grid container spacing={3} justifyContent="center" sx={{ mt: 3 }}>
              {/* Force items to stay on one row by specifying fixed widths at different breakpoints */}
              <Grid {...{component: "div", item: true, xs: 12, md: 4, sm: 4} as any}>
                <Box sx={{ 
                  p: 2, 
                  textAlign: 'center',
                  borderRadius: 2,
                  height: '100%', // Make boxes the same height
                  width: '300px',
                  bgcolor: alpha(theme.palette.primary.main, 0.07)
                }}>
                  <Typography variant="h5" component="div" sx={{ fontWeight: 700, mb: 1 }}>
                    Auditable
                  </Typography>
                  <Typography variant="body2">
                    Access verified trading history and performance metrics
                  </Typography>
                </Box>
              </Grid>
              
              <Grid {...{component: "div", item: true, xs: 12, md: 4, sm: 4} as any}>
                <Box sx={{ 
                  p: 2, 
                  textAlign: 'center',
                  borderRadius: 2,
                  height: '100%',
                  width: '300px',
                  bgcolor: alpha(theme.palette.primary.main, 0.07)
                }}>
                  <Typography variant="h5" component="div" sx={{ fontWeight: 700, mb: 1 }}>
                    Robust
                  </Typography>
                  <Typography variant="body2">
                    Performance data validated through our simulation platform
                  </Typography>
                </Box>
              </Grid>
              
              <Grid {...{component: "div", item: true, xs: 12, md: 4, sm: 4} as any}>
                <Box sx={{ 
                  p: 2, 
                  textAlign: 'center',
                  borderRadius: 2,
                  height: '100%',
                  width: '300px',
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
                transition: 'all 0.3s ease',
                border: '2px solid',
                borderColor: 'primary.main',
                '&:hover': {
                  backgroundColor: alpha(theme.palette.background.default, 0.75),
                  borderColor: theme.palette.primary.main,
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