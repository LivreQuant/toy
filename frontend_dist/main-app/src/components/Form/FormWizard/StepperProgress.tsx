// src/components/Form/FormWizard/StepperProgress.tsx
import React from 'react';
import { Box, Stepper, Step, StepLabel, useTheme } from '@mui/material';

interface StepperProgressProps {
  steps: string[];
  activeStep: number;
  completed?: boolean[];
  alternativeLabel?: boolean;
}

export const StepperProgress: React.FC<StepperProgressProps> = ({
  steps,
  activeStep,
  completed = [],
  alternativeLabel = true
}) => {
  const theme = useTheme();

  return (
    <Box sx={{ width: '100%', mb: 4 }}>
      <Stepper 
        activeStep={activeStep} 
        alternativeLabel={alternativeLabel}
        sx={{
          '& .MuiStepConnector-line': {
            borderTopWidth: 3,
          },
          '& .MuiStepLabel-label': {
            fontSize: '0.875rem',
            fontWeight: 500,
          },
          '& .MuiStepIcon-root': {
            fontSize: '1.5rem',
          }
        }}
      >
        {steps.map((label, index) => (
          <Step key={label} completed={completed[index]}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>
    </Box>
  );
};