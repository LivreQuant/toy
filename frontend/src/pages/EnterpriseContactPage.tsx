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
  Alert
} from '@mui/material';
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
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    company: '',
    role: '',
    institutionType: '',
    assetsUnderManagement: '',
    message: ''
  });
  const [success, setSuccess] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Here you would handle the form submission to your backend
    console.log('Form submitted:', formData);
    
    // Show success message
    setSuccess(true);
    
    // Reset form
    setFormData({
      name: '',
      email: '',
      company: '',
      role: '',
      institutionType: '',
      assetsUnderManagement: '',
      message: ''
    });
  };

  return (
    <Box sx={{ bgcolor: '#f5f7fa', minHeight: '100vh', py: 6 }}>
      <Container maxWidth="md">
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/')}
          sx={{ mb: 4 }}
        >
          Back to Home
        </Button>
        
        <Paper elevation={3} sx={{ p: 4, borderRadius: 3 }}>
          <Typography variant="h4" component="h1" gutterBottom sx={{ mb: 4 }}>
            Enterprise Consultation Request
          </Typography>
          
          <Typography variant="body1" paragraph>
            Complete the form below to schedule a consultation with our team. We'll discuss how our platform can help your institution identify and evaluate investment talent.
          </Typography>
          
          <form onSubmit={handleSubmit}>
            <Grid container spacing={3}>
              <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
                <TextField
                  required
                  fullWidth
                  label="Full Name"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                />
              </Grid>
              
              <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
                <TextField
                  required
                  fullWidth
                  label="Email Address"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                />
              </Grid>
              
              <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
                <TextField
                  required
                  fullWidth
                  label="Company/Institution"
                  name="company"
                  value={formData.company}
                  onChange={handleChange}
                />
              </Grid>
              
              <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
                <TextField
                  required
                  fullWidth
                  label="Your Role"
                  name="role"
                  value={formData.role}
                  onChange={handleChange}
                />
              </Grid>
              
              <Grid {...{component: "div", item: true, xs: 12, sm: 6} as any}>
                <TextField
                  select
                  required
                  fullWidth
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
              
              <Grid {...{component: "div", item: true, xs: 12} as any}>
                <TextField
                  fullWidth
                  label="Assets Under Management (optional)"
                  name="assetsUnderManagement"
                  value={formData.assetsUnderManagement}
                  onChange={handleChange}
                  placeholder="e.g., $500M-1B"
                />
              </Grid>
              
              <Grid {...{component: "div", item: true, xs: 12} as any}>
                <TextField
                  required
                  fullWidth
                  multiline
                  rows={4}
                  label="How can we help your institution?"
                  name="message"
                  value={formData.message}
                  onChange={handleChange}
                />
              </Grid>
              
              <Grid {...{component: "div", item: true, xs: 12} as any}>
                <Button
                  type="submit"
                  variant="contained"
                  color="primary"
                  size="large"
                  fullWidth
                  sx={{
                    py: 1.5,
                    mt: 2,
                    fontWeight: 600
                  }}
                >
                  Submit Request
                </Button>
              </Grid>
            </Grid>
          </form>
        </Paper>
      </Container>
      
      <Snackbar 
        open={success} 
        autoHideDuration={6000} 
        onClose={() => setSuccess(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setSuccess(false)} severity="success" sx={{ width: '100%' }}>
          Your consultation request has been submitted successfully! Our team will contact you shortly.
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default EnterpriseContactPage;