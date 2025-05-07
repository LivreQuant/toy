import React, { useState, forwardRef } from 'react';
import { Link } from 'react-router-dom';
import { 
  Box, 
  Container, 
  Typography, 
  Button, 
  Grid, 
  Stack, 
  useTheme,
  Dialog, 
  DialogTitle, 
  DialogContent, 
  DialogActions,
  TextField
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import backgroundImage from '../../assets/hero/yarn.png';
import dashImage from '../../assets/hero/dashboard.png';
import factImage from '../../assets/hero/factsheet.jpg';

interface HeroProps {
  className?: string;
}

const Hero = forwardRef<HTMLDivElement, HeroProps>(({ className }, ref) => {
  const theme = useTheme();
  
  // State for consultation form
  const [showConsultationForm, setShowConsultationForm] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    company: '',
    message: ''
  });

  // Handle form input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // Handle form submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Handle form submission logic here
    console.log('Form submitted:', formData);
    
    // Reset form and close dialog
    setFormData({
      name: '',
      email: '',
      company: '',
      message: ''
    });
    setShowConsultationForm(false);
  };
  
  return (
    <Box 
      ref={ref}
      className={className}
      sx={{ 
        pt: 12,           // Keep original top padding
        pb: 4,            // Reduced bottom padding (was 10)
        background: theme.palette.mode === 'dark' 
          ? 'linear-gradient(120deg,rgb(158, 7, 7) 0%,rgb(26, 126, 43) 100%)' 
          : 'linear-gradient(120deg, #f8f9fa 0%, #e3f2fd 100%)',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      {/* PNG Background - unchanged */}
      <Box
        sx={{
          position: 'absolute',
          top: -50,
          left: -300,
          right: 0,
          bottom: 0,
          zIndex: 0,
          opacity: 0.2,
          backgroundImage: `url(${backgroundImage})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          transform: 'rotate(-15deg) scale(1.25)',
          pointerEvents: 'none'
        }}
      />

      {/* SVG Pattern - unchanged */}
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          zIndex: 0,
          opacity: 0.2,
          pointerEvents: 'none'
        }}
      >
        <svg
          width="100%"
          height="100%"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 1440 320"
          preserveAspectRatio="xMidYMid slice"
        >
          <path
            fill={theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.05)'}
            d="M0,192L48,197.3C96,203,192,213,288,229.3C384,245,480,267,576,250.7C672,235,768,181,864,181.3C960,181,1056,235,1152,234.7C1248,235,1344,181,1392,154.7L1440,128L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z"
          ></path>
          <path
            fill={theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.025)'}
            d="M0,96L48,128C96,160,192,224,288,213.3C384,203,480,117,576,117.3C672,117,768,203,864,202.7C960,203,1056,117,1152,117.3C1248,117,1344,203,1392,245.3L1440,288L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z"
          ></path>
        </svg>
      </Box>

      {/* Main Content - unchanged except for the container margin */}
      <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1, mb: 0 }}>
        <Grid container spacing={4} alignItems="center">
          {/* Left content side - unchanged */}
          <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
          <Typography 
            variant="h2" 
            component="h2" 
            gutterBottom
            sx={{ 
                fontWeight: 800,
                lineHeight: 1.2,
                mb: 3,
                maxWidth: '600px', // Limit the maximum width
                width: '100%', // Ensure it takes full width up to maxWidth
                background: theme.palette.mode === 'dark'
                ? 'linear-gradient(90deg, #f5f5f5, #bbdefb)'
                : 'linear-gradient(90deg, #232526, #414345)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
            }}
            >
              The Digital Twin Fund Simulator
            </Typography>
            <Typography
              variant="h6"
              color="textSecondary"
              paragraph
              sx={{ 
                  mb: 4,
                  maxWidth: '500px', // Limit the maximum width
                  width: '100%' // Ensure it takes full width up to maxWidth
              }}
            >
              Our platform provides a realistic, risk-free environment to demonstrate and prove your investment aptitude so you can stand out from the crowd.
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
                      transition: 'all 0.3s ease',
                      border: '2px solid',             // Add border with current color
                      borderColor: theme.palette.primary.main,  // Keep border visible on hover
                      '&:hover': {
                          transform: 'translateY(-5px)',
                          boxShadow: '0 8px 20px rgba(33, 150, 243, 0.5)',
                          backgroundColor: alpha(theme.palette.background.default, 0.75),
                          border: '2px solid',
                          borderColor: theme.palette.primary.main,  // Keep border visible on hover
                      }
                    }}
                >
                    Get Started
                </Button>
              
                {/* Consultation Request Button */}
                <Button 
                  onClick={() => setShowConsultationForm(true)}
                  variant="outlined"
                  color="primary"
                  size="large"
                  sx={{
                    py: 1.5,
                    px: 3,
                    fontWeight: 600,
                    borderWidth: 2,
                    transition: 'all 0.3s ease',
                    backgroundColor: alpha(theme.palette.background.default, 0.5),
                    '&:hover': {
                      transform: 'translateY(-5px)',
                      backgroundColor: `${theme.palette.background.default} !important`,
                    }
                  }}
                >
                  Request Consultation
                </Button>
            </Stack>
          </Grid>
          
          {/* Right side with platform and charts - unchanged */}
          <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
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
                    width: 250,
                    height: 'auto', // Allow height to adjust based on aspect ratio
                    maxHeight: 500, // Optional: set a maximum height
                    aspectRatio: '9/10', // Set a specific aspect ratio if desired
                    top: 50,
                    left: 220,
                    animation: 'float 20s ease-in-out infinite reverse',
                    backgroundImage: `url(${factImage})`, // Import your image at the top of the file
                    backgroundSize: 'cover', // This ensures the image covers the entire box
                    backgroundPosition: 'center', // Centers the image
                    backgroundRepeat: 'no-repeat', // Prevents image from repeating
                    backgroundColor: 'background.paper',
                    borderRadius: 1,
                    },
                    '& .chart-2': {
                    width: 500,
                    height: 'auto', // Allow height to adjust based on aspect ratio
                    maxHeight: 250, // Optional: set a maximum height
                    aspectRatio: '25/10', // Set a specific aspect ratio if desired
                    top: 250,
                    left: 0,
                    animation: 'float 20s ease-in-out infinite',
                    backgroundImage: `url(${dashImage})`, // Import your image at the top of the file
                    backgroundSize: 'cover', // This ensures the image covers the entire box
                    backgroundPosition: 'center', // Centers the image
                    backgroundRepeat: 'no-repeat', // Prevents image from repeating
                    backgroundColor: 'background.paper',
                    borderRadius: 1,
                    },
                }}
                >
                <Box className="platform-preview" />
                <Box className="floating-chart chart-1" />
                <Box className="floating-chart chart-2" />
                </Box>
          </Grid>
        </Grid>
      </Container>

      {/* Consultation Form Dialog */}
      <Dialog 
        open={showConsultationForm} 
        onClose={() => setShowConsultationForm(false)}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>Request a Consultation</DialogTitle>
        <form onSubmit={handleSubmit}>
          <DialogContent>
            <Stack spacing={3}>
              <TextField
                label="Name"
                name="name"
                value={formData.name}
                onChange={handleInputChange}
                fullWidth
                required
              />
              <TextField
                label="Email"
                name="email"
                type="email"
                value={formData.email}
                onChange={handleInputChange}
                fullWidth
                required
              />
              <TextField
                label="Company"
                name="company"
                value={formData.company}
                onChange={handleInputChange}
                fullWidth
              />
              <TextField
                label="Message"
                name="message"
                value={formData.message}
                onChange={handleInputChange}
                multiline
                rows={4}
                fullWidth
                required
              />
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 3 }}>
            <Button 
              onClick={() => setShowConsultationForm(false)} 
              color="inherit"
            >
              Cancel
            </Button>
            <Button 
              type="submit" 
              variant="contained" 
              color="primary"
            >
              Submit Request
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Box>
  );
});

export default Hero;