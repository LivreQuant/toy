// src/components/landing/Footer.tsx
import React from 'react';
import { Link } from 'react-router-dom';
import { Box, Container, Typography, Button, Grid, Divider, useTheme } from '@mui/material';

const footerLinks = [
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
];

const socialLinks = ['LinkedIn', 'Twitter', 'Facebook', 'Instagram'];

const Footer: React.FC = () => {
  const theme = useTheme();
  
  return (
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
          <Grid {...{component: "div", item: true, xs: 12, md: 4} as any}>
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
          
          <Grid {...{component: "div", item: true, xs: 12, md: 8} as any}>
            <Grid container spacing={4}>
              {footerLinks.map((column, index) => (
                <Grid {...{component: "div", item: true, xs: 6, sm: 3, key: index} as any}>
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
            {socialLinks.map((social) => (
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
  );
};

export default Footer;