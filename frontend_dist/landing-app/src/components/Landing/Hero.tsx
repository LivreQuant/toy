import React, { useState, forwardRef } from 'react';
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
import { appUrlService } from '../../config';

import { HERO_IMAGES } from '@trading-app/assets';

const backgroundImage = HERO_IMAGES.YARN;
const dashImage = HERO_IMAGES.DASHBOARD;
const factImage = HERO_IMAGES.FACTSHEET;

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

  // Handle navigation to main app
  const handleGetStarted = () => {
    const signupUrl = appUrlService.getMainAppRoute('signup');
    window.location.href = signupUrl;
  };

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
        pt: 12,
        pb: 4,
        background: theme.palette.mode === 'dark' 
          ? 'linear-gradient(120deg,rgb(158, 7, 7) 0%,rgb(26, 126, 43) 100%)' 
          : 'linear-gradient(120deg, #f8f9fa 0%, #e3f2fd 100%)',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      {/* Background elements remain the same... */}
      
      {/* Main Content */}
      <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1, mb: 0 }}>
        <Grid container spacing={4} alignItems="center">
          {/* Left content side */}
          <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
            <Typography 
              variant="h2" 
              component="h2" 
              gutterBottom
              sx={{ 
                fontWeight: 800,
                lineHeight: 1.2,
                mb: 3,
                maxWidth: '600px',
                width: '100%',
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
                maxWidth: '500px',
                width: '100%'
              }}
            >
              Our platform provides a realistic, risk-free environment for you to demonstrate and prove your investment aptitude so you can stand out from the crowd.
            </Typography>
            
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <Button 
                onClick={handleGetStarted}
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
                  border: '2px solid',
                  borderColor: theme.palette.primary.main,
                  '&:hover': {
                    transform: 'translateY(-5px)',
                    boxShadow: '0 8px 20px rgba(33, 150, 243, 0.5)',
                    backgroundColor: alpha(theme.palette.background.default, 0.75),
                    border: '2px solid',
                    borderColor: theme.palette.primary.main,
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
         
         {/* Right side with platform and charts */}
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
                 height: 'auto',
                 maxHeight: 500,
                 aspectRatio: '9/10',
                 top: 50,
                 left: 220,
                 animation: 'float 20s ease-in-out infinite reverse',
                 backgroundImage: `url(${factImage})`,
                 backgroundSize: 'cover',
                 backgroundPosition: 'center',
                 backgroundRepeat: 'no-repeat',
                 backgroundColor: 'background.paper',
                 borderRadius: 1,
               },
               '& .chart-2': {
                 width: 500,
                 height: 'auto',
                 maxHeight: 250,
                 aspectRatio: '25/10',
                 top: 250,
                 left: 0,
                 animation: 'float 20s ease-in-out infinite',
                 backgroundImage: `url(${dashImage})`,
                 backgroundSize: 'cover',
                 backgroundPosition: 'center',
                 backgroundRepeat: 'no-repeat',
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