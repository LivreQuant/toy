// src/pages/LandingPage.tsx
import React, { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { 
  Box, 
  Container,
  Typography,
  Button, 
  Grid,
  Card,
  CardContent,
  useTheme,
  Paper,
  Divider,
  Stack
} from '@mui/material';
import './LandingPage.css';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext'; // Your custom theme hook

const LandingPage: React.FC = () => {
  const theme = useTheme(); // Material UI theme
  const { mode, toggleTheme } = useCustomTheme(); // Your custom theme context
  
  // Refs for scroll animation elements
  const heroRef = useRef<HTMLDivElement>(null);
  const featuresRef = useRef<HTMLDivElement>(null);
  const testimonialsRef = useRef<HTMLDivElement>(null);
  
  // Set up animations
  useEffect(() => {
    // Intersection Observer for scroll animations
    const observerOptions = {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animated-in');
        }
      });
    }, observerOptions);
    
    // Observe all animation elements
    const elements = [heroRef.current, featuresRef.current, testimonialsRef.current];
    elements.forEach(el => el && observer.observe(el));
    
    return () => {
      elements.forEach(el => el && observer.unobserve(el));
    };
  }, []);

  return (
    <Box 
      sx={{ 
        bgcolor: 'background.default',
        color: 'text.primary',
        minHeight: '100vh'
      }}
    >
      {/* Header */}
      <Paper 
        elevation={1}
        sx={{ 
          position: 'sticky', 
          top: 0, 
          zIndex: 100,
          borderRadius: 0,
          py: 2
        }}
      >
        <Container maxWidth="lg">
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Box 
                sx={{ 
                  width: 40, 
                  height: 40, 
                  bgcolor: 'primary.main', 
                  borderRadius: 2,
                  mr: 2
                }} 
              />
              <Typography 
                variant="h4" 
                component="h1" 
                sx={{ 
                  background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.primary.light})`,
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  fontWeight: 'bold'
                }}
              >
                Quantum Trade
              </Typography>
            </Box>
            
            <Box sx={{ display: { xs: 'none', md: 'flex' }, gap: 4 }}>
              <Button color="inherit" href="#features">Features</Button>
              <Button color="inherit" href="#how-it-works">How It Works</Button>
              <Button color="inherit" href="#testimonials">Testimonials</Button>
            </Box>
            
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button 
                component={Link} 
                to="/login" 
                variant="outlined" 
                color="primary"
              >
                Log In
              </Button>
              <Button 
                component={Link} 
                to="/signup" 
                variant="contained" 
                color="primary"
              >
                Get Started
              </Button>
            </Box>
          </Box>
        </Container>
      </Paper>

      {/* Hero Section */}
      <Box 
        ref={heroRef}
        className="animate-on-scroll"
        sx={{ 
          pt: 12, 
          pb: 10,
          background: theme.palette.mode === 'dark' 
            ? 'linear-gradient(120deg, #121212 0%, #1a237e 100%)' 
            : 'linear-gradient(120deg, #f8f9fa 0%, #e3f2fd 100%)',
          position: 'relative',
          overflow: 'hidden'
        }}
      >
        <Container maxWidth="lg">
          <Grid container spacing={4} alignItems="center">
            <Grid component="div" item xs={12} md={6}>
              <Typography 
                variant="h2" 
                component="h2" 
                gutterBottom
                sx={{ 
                  fontWeight: 800,
                  lineHeight: 1.2,
                  mb: 3,
                  background: theme.palette.mode === 'dark'
                    ? 'linear-gradient(90deg, #f5f5f5, #bbdefb)'
                    : 'linear-gradient(90deg, #232526, #414345)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}
              >
                Advanced Trading Simulator for Financial Professionals
              </Typography>
              
              <Typography 
                variant="h6" 
                color="textSecondary" 
                paragraph
                sx={{ mb: 4 }}
              >
                Develop and test your trading strategies in a risk-free environment with real-time market data and comprehensive analytics.
              </Typography>
              
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
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
                    boxShadow: '0 8px 20px rgba(33, 150, 243, 0.3)',
                    fontWeight: 600,
                    '&:hover': {
                      transform: 'translateY(-3px)',
                      boxShadow: '0 12px 28px rgba(33, 150, 243, 0.4)',
                    }
                  }}
                >
                  Start Free Trial
                </Button>
                
                <Button 
                  component={Link} 
                  to="/demo" 
                  variant="text" 
                  color="primary"
                  size="large"
                  startIcon={<span>▶</span>}
                  sx={{ 
                    py: 1.5,
                    fontWeight: 600,
                    '&:hover': {
                      transform: 'translateY(-3px)',
                    }
                  }}
                >
                  Watch Demo
                </Button>
              </Stack>
            </Grid>
            
            <Grid component="div" item xs={12} md={6}>
              <Box 
                sx={{ 
                  position: 'relative',
                  height: 500,
                  '& .platform-preview': {
                    position: 'absolute',
                    width: '100%',
                    height: '100%',
                    borderRadius: 3,
                    boxShadow: '0 20px 80px rgba(0, 0, 0, 0.12)',
                    backgroundColor: 'background.paper',
                  },
                  '& .floating-chart': {
                    position: 'absolute',
                    backgroundColor: 'background.paper',
                    borderRadius: 2,
                    boxShadow: '0 10px 30px rgba(0, 0, 0, 0.1)',
                  },
                  '& .chart-1': {
                    width: 180,
                    height: 120,
                    top: -30,
                    right: 40,
                    animation: 'float 6s ease-in-out infinite',
                  },
                  '& .chart-2': {
                    width: 220,
                    height: 150,
                    bottom: -20,
                    left: 30,
                    animation: 'float 8s ease-in-out infinite reverse',
                  }
                }}
              >
                <Box className="platform-preview" />
                <Box className="floating-chart chart-1" />
                <Box className="floating-chart chart-2" />
              </Box>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* Trusted By Section */}
      <Box sx={{ py: 5, bgcolor: 'background.default', borderBottom: 1, borderColor: 'divider' }}>
        <Container maxWidth="lg" sx={{ textAlign: 'center' }}>
          <Typography variant="h6" color="textSecondary" gutterBottom>
            Trusted by top institutions
          </Typography>
          
          <Grid container spacing={4} justifyContent="center" sx={{ mt: 2 }}>
            {[1, 2, 3, 4, 5].map((item) => (
              <Grid component="div" item key={item}>
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

      {/* Features Section */}
      <Box 
        id="features"
        ref={featuresRef}
        className="animate-on-scroll"
        sx={{ py: 10 }}
      >
        <Container maxWidth="lg" sx={{ textAlign: 'center' }}>
          <Typography variant="h3" component="h2" gutterBottom>
            Professional Trading Features
          </Typography>
          
          <Typography variant="h6" color="textSecondary" sx={{ mb: 6, maxWidth: 700, mx: 'auto' }}>
            Everything you need to build and test sophisticated trading strategies
          </Typography>
          
          <Grid container spacing={4}>
            {[
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
            ].map((feature, index) => (
              <Grid component="div" item xs={12} md={6} lg={4} key={index}>
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
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* How It Works Section */}
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
            Start simulating your trading strategies in minutes
          </Typography>
          
          <Grid container spacing={4}>
            {[
              {
                step: 1,
                title: 'Create Your Book',
                description: 'Configure your trading book with custom parameters, capital allocation, and risk limits.'
              },
              {
                step: 2,
                title: 'Develop Strategy',
                description: 'Build and refine your trading strategies using our intuitive interface or API integration.'
              },
              {
                step: 3,
                title: 'Simulate & Analyze',
                description: 'Run your strategies in our realistic market environment and analyze performance in real-time.'
              }
            ].map((step) => (
              <Grid component="div" item xs={12} md={4} key={step.step}>
                <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
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
                  
                  <Typography variant="h5" component="h3" gutterBottom sx={{ fontWeight: 600 }}>
                    {step.title}
                  </Typography>
                  
                  <Typography variant="body1" color="textSecondary" paragraph>
                    {step.description}
                  </Typography>
                  
                  <Box 
                    sx={{ 
                      mt: 'auto',
                      width: '100%',
                      height: 200,
                      bgcolor: 'background.paper',
                      borderRadius: 2,
                      boxShadow: '0 10px 30px rgba(0, 0, 0, 0.08)'
                    }} 
                  />
                </Box>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* Stats Section */}
      <Box 
        sx={{ 
          py: 8,
          background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.primary.light})`,
        }}
      >
        <Container maxWidth="lg">
          <Grid container spacing={3}>
            {[
              { value: '10M+', label: 'Orders Processed Daily' },
              { value: '$250B+', label: 'Simulated Trading Volume' },
              { value: '5,000+', label: 'Professional Traders' },
              { value: '99.9%', label: 'Platform Uptime' }
            ].map((stat, index) => (
              <Grid component="div" item xs={6} md={3} key={index}>
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

      {/* Testimonials */}
      <Box 
        id="testimonials"
        ref={testimonialsRef}
        className="animate-on-scroll"
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

      {/* CTA Section */}
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
            <Grid component="div" item xs={12} md={6}>
              <Typography variant="h3" component="h2" gutterBottom>
                Ready to transform your trading strategy?
              </Typography>
              
              <Typography variant="h6" color="textSecondary" paragraph>
                Join thousands of professional traders using our platform today.
              </Typography>
              
              <Button 
                component={Link} 
                to="/signup" 
                variant="contained" 
                color="primary"
                size="large"
                sx={{ 
                  mt: 2,
                  py: 1.5, 
                  px: 4,
                  borderRadius: 2,
                  fontWeight: 600
                }}
              >
                Start Your Free Trial
              </Button>
            </Grid>
            
            <Grid component="div" item xs={12} md={6}>
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

      {/* Footer */}
      <Box 
        component="footer" 
        sx={{ 
          bgcolor: theme.palette.mode === 'dark' ? '#1a1a1a' : '#222',
          color: 'white',
          py: 8 
        }}
      >
        <Container maxWidth="lg">
          <Grid container spacing={6}>
            <Grid component="div" item xs={12} md={4}>
              <Typography 
                variant="h4" 
                component="div" 
                sx={{ 
                  mb: 4,
                  background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.primary.light})`,
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}
              >
                Quantum Trade
              </Typography>
            </Grid>
            
            <Grid component="div" item xs={12} md={8}>
              <Grid container spacing={4}>
                {[
                  {
                    title: 'Platform',
                    links: ['Features', 'How It Works', 'Pricing', 'Enterprise']
                  },
                  {
                    title: 'Company',
                    links: ['About Us', 'Blog', 'Careers', 'Contact']
                  },
                  {
                    title: 'Resources',
                    links: ['Documentation', 'API Reference', 'Help Center', 'Community']
                  },
                  {
                    title: 'Legal',
                    links: ['Terms of Service', 'Privacy Policy', 'Security']
                  }
                ].map((column, index) => (
                  <Grid component="div" item xs={6} sm={3} key={index}>
                    <Typography variant="h6" component="h4" gutterBottom>
                      {column.title}
                    </Typography>
                    
                    <Box component="ul" sx={{ p: 0, m: 0, listStyle: 'none' }}>
                      {column.links.map((link, i) => (
                        <Box component="li" key={i} sx={{ mb: 1 }}>
                          <Button 
                            component={Link} 
                            to="#" 
                            sx={{ 
                              p: 0, 
                              color: 'rgba(255,255,255,0.7)',
                              textTransform: 'none',
                              '&:hover': {
                                color: theme.palette.primary.light
                              }
                            }}
                          >
                            {link}
                          </Button>
                        </Box>
                      ))}
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </Grid>
          </Grid>
          
          <Divider sx={{ my: 4, bgcolor: 'rgba(255,255,255,0.1)' }} />
          
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' }}>
            <Typography variant="body2" color="rgba(255,255,255,0.5)">
              &copy; {new Date().getFullYear()} Quantum Trade. All rights reserved.
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 2 }}>
              {['LinkedIn', 'Twitter', 'Facebook', 'Instagram'].map((social) => (
                <Box 
                  key={social}
                  sx={{ 
                    width: 40, 
                    height: 40, 
                    borderRadius: '50%', 
                    bgcolor: 'rgba(255,255,255,0.1)',
                    transition: 'background-color 0.3s',
                    '&:hover': {
                      bgcolor: theme.palette.primary.main
                    }
                  }} 
                />
              ))}
            </Box>
          </Box>
        </Container>
      </Box>
    </Box>
  );
};

export default LandingPage;