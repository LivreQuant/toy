// src/components/Form/FormWizard/FormWizard.tsx
import React, { useState, useCallback, ReactNode } from 'react';
import { Box, Paper, Stepper, Step, StepLabel, Divider } from '@mui/material';
import { FormActions } from '../FormLayouts/FormActions'; // Fix the import path

export interface FormWizardProps {
  steps: Array<{
    label: string;
    content: ReactNode;
    validate?: () => boolean | string;
  }>;
  onSubmit: (formData: any) => Promise<{ success: boolean; error?: string }>;
  submitButtonText: string;
  title: string;
  subtitle?: string;
  onBack?: () => void;
  isSubmitting?: boolean;
}

export const FormWizard: React.FC<FormWizardProps> = ({
  steps,
  onSubmit,
  submitButtonText,
  title,
  subtitle,
  onBack,
  isSubmitting = false
}) => {
  const [activeStep, setActiveStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleNext = useCallback(() => {
    const currentStep = steps[activeStep];
    if (currentStep.validate && !currentStep.validate()) {
      return;
    }
    setActiveStep(prev => prev + 1);
  }, [activeStep, steps]);

  const handlePrevious = useCallback(() => {
    setActiveStep(prev => prev - 1);
  }, []);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    
    const currentStep = steps[activeStep];
    if (currentStep.validate && !currentStep.validate()) {
      return;
    }
    
    try {
      const result = await onSubmit({});
      if (!result.success) {
        setErrors({ submit: result.error || 'Submission failed' });
      }
    } catch (error: any) {
      setErrors({ submit: error.message });
    }
  }, [activeStep, steps, onSubmit]);

  const isLastStep = activeStep === steps.length - 1;
  const isFirstStep = activeStep === 0;

  return (
    <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
      {onBack && (
        <Box sx={{ mb: 2 }}>
          <button onClick={onBack}>← Back</button>
        </Box>
      )}
      
      <Paper elevation={3} sx={{ p: 4 }}>
        <Box sx={{ textAlign: 'center', mb: 4 }}>
          <h1>{title}</h1>
          {subtitle && <p>{subtitle}</p>}
        </Box>
        
        <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
          {steps.map((step, index) => (
            <Step key={index}>
              <StepLabel>{step.label}</StepLabel>
            </Step>
          ))}
        </Stepper>
        
        <Divider sx={{ mb: 4 }} />
        
        <form onSubmit={isLastStep ? handleSubmit : (e) => { e.preventDefault(); handleNext(); }}>
          {steps[activeStep]?.content}
          
          <FormActions
            onPrevious={!isFirstStep ? handlePrevious : undefined}
            onNext={!isLastStep ? handleNext : undefined}
            onSubmit={isLastStep ? handleSubmit : undefined}
            submitButtonText={submitButtonText}
            isSubmitting={isSubmitting}
            nextDisabled={false}
          />
        </form>
      </Paper>
    </Box>
  );
};