// src/pages/EnterpriseContactPage.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  TextField,
  Button,
  Grid,
  Paper,
  MenuItem,
  Snackbar,
  Alert,
  useTheme
  // CircularProgress // Optional for loading state
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

const institutionTypes = [
  'Endowment',
  'Pension Fund',
  'Fund of Funds',
  'Family Office',
  'Hedge Fund',
  'Asset Manager',
  'Investment Committee',
  'Other'
];

const EnterpriseContactPage: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();

  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    email: '',
    company: '',
    role: '',
    institutionType: '',
    message: ''
  });
  const [success, setSuccess] = useState(false);
  // const [loading, setLoading] = useState(false); // Optional

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // setLoading(true); // Optional
    // Here you would handle the form submission to your backend
    console.log('Form submitted:', formData);

    // Simulate API call
    // await new Promise(resolve => setTimeout(resolve, 1000));

    setSuccess(true);
    // setLoading(false); // Optional

    // Reset form
    setFormData({
      firstName: '',
      lastName: '',
      email: '',
      company: '',
      role: '',
      institutionType: '',
      message: ''
    });
  };

  const handleCloseSnackbar = (event?: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') {
      return;
    }
    setSuccess(false);
  };

  return (
    <Box sx={{ bgcolor: '#f5f7fa', minHeight: '100vh', py: { xs: 4, sm: 6 } }}>
      <Container sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }} maxWidth="md">

        {/* Main Form Paper */}
        <Paper 
          elevation={0}
          sx={{ 
            p: { xs: 3, sm: 4 },
            borderRadius: 2,
            boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.05)'
          }}
        >
          {/* Title and Description */}
          <Typography 
            variant="h4" 
            component="h1" 
            gutterBottom 
            sx={{ 
              mb: 2,
              fontWeight: 'bold',
              textAlign: 'center',
              color: 'primary.main'
            }}
          >
            Enterprise Consultation Request
          </Typography>

          <Typography 
            variant="body1" 
            paragraph
            sx={{ 
              mb: 4,
              textAlign: 'center',
              color: 'text.secondary'
            }}
          >
            Complete the form below to schedule a consultation with our team. We'll discuss how our platform can help your institution identify and evaluate investment talent.
          </Typography>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            <Grid container spacing={3}>
              {/* First & Last Name in same row */}
              <Grid {...{component: "div", item: true, size: 6} as any}>
                <TextField
                  required
                  fullWidth
                  variant="outlined"
                  label="First Name"
                  name="firstName"
                  value={formData.firstName}
                  onChange={handleChange}
                />
              </Grid>
              <Grid {...{component: "div", item: true, size: 6} as any}>
                <TextField
                  required
                  fullWidth
                  variant="outlined"
                  label="Last Name"
                  name="lastName"
                  value={formData.lastName}
                  onChange={handleChange}
                />
              </Grid>

              {/* Email on its own row */}
              <Grid {...{component: "div", item: true, size: 6} as any}>
                <TextField
                  required
                  fullWidth
                  variant="outlined"
                  label="Email Address"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                />
              </Grid>
              <Grid {...{component: "div", item: true, size: 6} as any}>
                <TextField
                  required
                  fullWidth
                  variant="outlined"
                  label="Your Role"
                  name="role"
                  value={formData.role}
                  onChange={handleChange}
                />
              </Grid>

              {/* Company / Role / Institution Type in same row */}
              <Grid {...{component: "div", item: true, size: 6} as any}>
                <TextField
                  required
                  fullWidth
                  variant="outlined"
                  label="Company/Institution"
                  name="company"
                  value={formData.company}
                  onChange={handleChange}
                />
              </Grid>
              <Grid {...{component: "div", item: true, size: 6} as any}>
                <TextField
                  select
                  required
                  fullWidth
                  variant="outlined"
                  label="Institution Type"
                  name="institutionType"
                  value={formData.institutionType}
                  onChange={handleChange}
                >
                  {institutionTypes.map(option => (
                    <MenuItem key={option} value={option}>
                      {option}
                    </MenuItem>
                  ))}
                </TextField>
              </Grid>

              {/* Message on its own row */}
              <Grid {...{component: "div", item: true, size: 12} as any}>
                <TextField
                  fullWidth
                  multiline
                  rows={4}
                  variant="outlined"
                  label="How can we help you?"
                  name="message"
                  value={formData.message}
                  onChange={handleChange}
                />
              </Grid>

              {/* Submit Button */}
              <Grid {...{component: "div", item: true, size: 12} as any}>
                <Box display="flex" justifyContent="flex-end">
                  <Button
                    type="submit"
                    variant="contained"
                    color="primary"
                    size="large"
                    sx={{
                      py: 1,         // Increased vertical padding
                      px: 2,           // Increased horizontal padding
                      fontWeight: 600,
                      borderRadius: 2,
                      textTransform: 'none',
                      display: 'flex',  // Added display flex
                      alignItems: 'center', // Added to center text vertically
                      justifyContent: 'center', // Added to center text horizontally
                      height: '48px'    // Set a fixed height
                    }}
                  >
                    Submit Request
                  </Button>
                </Box>
              </Grid>
            </Grid>
          </form>          
        </Paper>

          
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/')}
          variant="contained" 
          color="secondary" 
          size="medium"
          sx={{
            py: 1,         // Increased vertical padding
            px: 2,           // Increased horizontal padding
            fontWeight: 600,
            marginTop: 2,
            width: '150px',
            borderRadius: 2,
            textTransform: 'none',
            display: 'flex',  // Added display flex
            align: 'center', // Added to center text vertically
            alignItems: 'center', // Added to center text vertically
            justifyContent: 'center', // Added to center text horizontally
            height: '48px'    // Set a fixed height
          }}
        >
          Back to Home
        </Button>

      </Container>

      {/* Success Snackbar */}
      <Snackbar
        open={success}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert 
          onClose={handleCloseSnackbar} 
          severity="success" 
          variant="filled"
          sx={{ width: '100%' }}
        >
          Your consultation request has been submitted successfully! Our team will contact you shortly.
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default EnterpriseContactPage;