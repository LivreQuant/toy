// src/components/Form/FormLayouts/FormActions.tsx
import React from 'react';
import { Box, Button, CircularProgress } from '@mui/material';

export interface FormActionsProps {
  onPrevious?: () => void;
  onNext?: () => void;
  onSubmit?: (e: React.FormEvent) => void;
  submitButtonText?: string;
  isSubmitting?: boolean;
  nextDisabled?: boolean;
  previousDisabled?: boolean;
}

export const FormActions: React.FC<FormActionsProps> = ({
  onPrevious,
  onNext,
  onSubmit,
  submitButtonText = 'Submit',
  isSubmitting = false,
  nextDisabled = false,
  previousDisabled = false
}) => {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4, pt: 2 }}>
      <Button
        disabled={!onPrevious || previousDisabled}
        onClick={onPrevious}
        variant="outlined"
      >
        Back
      </Button>
      
      {onNext ? (
        <Button 
          variant="contained" 
          color="primary" 
          onClick={onNext}
          disabled={nextDisabled}
        >
          Next
        </Button>
      ) : (
        <Button 
          variant="contained" 
          color="primary" 
          onClick={onSubmit}
          disabled={isSubmitting}
          type="submit"
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
      )}
    </Box>
  );
};