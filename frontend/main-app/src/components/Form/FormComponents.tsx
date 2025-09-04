// src/components/Form/FormComponents.tsx
import React from 'react';
import {
  Box,
  Button,
  Paper,
  Stepper,
  Step,
  StepLabel,
  Typography,
  Divider,
  ToggleButtonGroup,
  ToggleButton,
  CircularProgress,
  FormHelperText
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';

// Simple form container wrapper
export interface FormContainerProps {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  children: React.ReactNode;
}

export const FormContainer: React.FC<FormContainerProps> = ({
  title,
  subtitle,
  onBack,
  children
}) => {
  return (
    <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
      {onBack && (
        <Button 
          startIcon={<ArrowBackIcon />} 
          onClick={onBack}
          variant="outlined"
          sx={{ mr: 2, mb: 4 }}
        >
          Back to Home
        </Button>
      )}
      
      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          {title}
        </Typography>
        
        {subtitle && (
          <Typography variant="subtitle1" color="text.secondary" paragraph align="center">
            {subtitle}
          </Typography>
        )}
        
        {children}
      </Paper>
    </Box>
  );
};

// Form stepper with navigation
export interface FormStepperProps {
  activeStep: number;
  steps: string[];
  onNext: () => void;
  onBack: () => void;
  onSubmit: (e: React.FormEvent) => void;
  isSubmitting: boolean;
  submitButtonText: string;
  children: React.ReactNode;
}


export const FormStepper: React.FC<FormStepperProps> = ({
    activeStep,
    steps,
    onNext,
    onBack,
    onSubmit,
    isSubmitting,
    submitButtonText,
    children
  }) => {
    const isLastStep = activeStep === steps.length - 1;
    const isFirstStep = activeStep === 0;
  
    // Handle form submission - only call onNext, never onSubmit automatically
    const handleFormSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      // Only call onNext, never auto-submit on last step
      if (!isLastStep) {
        onNext();
      }
      // Do nothing on last step - wait for explicit submit button click
    };
  
    // Handle explicit submit button click
    const handleSubmitClick = (e: React.MouseEvent) => {
      e.preventDefault();
      onSubmit(e as any); // Cast to React.FormEvent for compatibility
    };
  
    return (
      <>
        <Stepper activeStep={activeStep} sx={{ mb: 4, pt: 2, pb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
        
        <Divider sx={{ mb: 4 }} />
        
        <form onSubmit={handleFormSubmit}>
          {children}
          
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4, pt: 2 }}>
            <Button
              disabled={isFirstStep}
              onClick={onBack}
              variant="outlined"
              type="button"
            >
              Back
            </Button>
            
            {isLastStep ? (
              <Button 
                variant="contained" 
                color="primary" 
                onClick={handleSubmitClick}
                disabled={isSubmitting}
                type="button"
              >
                {isSubmitting ? (
                  <>
                    <CircularProgress size={24} sx={{ mr: 1 }} />
                    {submitButtonText}...
                  </>
                ) : (
                  submitButtonText
                )}
              </Button>
            ) : (
              <Button 
                variant="contained" 
                color="primary" 
                onClick={onNext}
                type="button"
              >
                Next
              </Button>
            )}
          </Box>
        </form>
      </>
    );
  };

// Reusable toggle button group
export interface ToggleOption {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

export interface FormToggleGroupProps {
  title: string;
  description?: string;
  options: ToggleOption[];
  value: string[];
  onChange: (value: string[]) => void;
  error?: string;
  required?: boolean;
}

export const FormToggleGroup: React.FC<FormToggleGroupProps> = ({
  title,
  description,
  options,
  value,
  onChange,
  error,
  required = false
}) => {
  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        {title} {required && <span style={{ color: 'red' }}>*</span>}
      </Typography>
      
      {description && (
        <Typography variant="body2" color="text.secondary" paragraph>
          {description}
        </Typography>
      )}
      
      <ToggleButtonGroup
        value={value}
        onChange={(_, newValue) => onChange(newValue || [])}
        aria-label={title}
        color="primary"
        fullWidth
      >
        {options.map((option) => (
          <ToggleButton 
            key={option.value} 
            value={option.value}
            disabled={option.disabled}
          >
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2">{option.label}</Typography>
              {option.description && (
                <Typography variant="caption" color="text.secondary" display="block">
                  {option.description}
                </Typography>
              )}
            </Box>
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      
      {error && (
        <FormHelperText error sx={{ mt: 1 }}>
          {error}
        </FormHelperText>
      )}
    </Box>
  );
};

// This export {} makes it a proper module
export {};