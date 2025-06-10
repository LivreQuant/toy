// src/components/Form/FormWizard/FormStep.tsx
import React from 'react';
import { Box, Fade, Slide } from '@mui/material';

interface FormStepProps {
  children: React.ReactNode;
  isActive: boolean;
  direction?: 'left' | 'right' | 'up' | 'down';
  animationType?: 'fade' | 'slide' | 'none';
  timeout?: number;
}

export const FormStep: React.FC<FormStepProps> = ({
  children,
  isActive,
  direction = 'left',
  animationType = 'fade',
  timeout = 300
}) => {
  if (animationType === 'none') {
    return isActive ? <Box>{children}</Box> : null;
  }

  if (animationType === 'slide') {
    return (
      <Slide
        direction={direction}
        in={isActive}
        timeout={timeout}
        mountOnEnter
        unmountOnExit
      >
        <Box>{children}</Box>
      </Slide>
    );
  }

  return (
    <Fade
      in={isActive}
      timeout={timeout}
      mountOnEnter
      unmountOnExit
    >
      <Box>{children}</Box>
    </Fade>
  );
};