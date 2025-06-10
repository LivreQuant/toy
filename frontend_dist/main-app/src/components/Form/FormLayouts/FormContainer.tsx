// src/components/Form/FormLayouts/FormContainer.tsx
import React from 'react';
import { Box, Paper, Typography, Button } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

export interface FormContainerProps {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  children: React.ReactNode;
  maxWidth?: number | string;
  elevation?: number;
  padding?: number;
}

export const FormContainer: React.FC<FormContainerProps> = ({
  title,
  subtitle,
  onBack,
  children,
  maxWidth = 1200,
  elevation = 3,
  padding = 4
}) => {
  return (
    <Box sx={{ p: 4, maxWidth, mx: 'auto' }}>
      {onBack && (
        <Button 
          startIcon={<ArrowBackIcon />} 
          onClick={onBack}
          variant="outlined"
          sx={{ mr: 2, mb: 4 }}
        >
          Back
        </Button>
      )}
      
      <Paper elevation={elevation} sx={{ p: padding }}>
        <Box sx={{ textAlign: 'center', mb: 4 }}>
          <Typography variant="h4" component="h1" gutterBottom>
            {title}
          </Typography>
          
          {subtitle && (
            <Typography variant="subtitle1" color="text.secondary" paragraph>
              {subtitle}
            </Typography>
          )}
        </Box>
        
        {children}
      </Paper>
    </Box>
  );
};