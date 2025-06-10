// src/components/Form/FormFields/ToggleButtonGroup.tsx (FIXED HORIZONTAL LAYOUT)
import React from 'react';
import { 
  Box, 
  Typography, 
  ToggleButtonGroup as MUIToggleButtonGroup, 
  ToggleButton,
  FormHelperText
} from '@mui/material';

interface Option {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

export interface ToggleButtonGroupProps {
  title: string;
  description?: string;
  options: Option[];
  value: string[];
  onChange: (value: string[]) => void;
  error?: string;
  required?: boolean;
  multiple?: boolean;
  fullWidth?: boolean;
}

export const ToggleButtonGroup: React.FC<ToggleButtonGroupProps> = ({
  title,
  description,
  options,
  value,
  onChange,
  error,
  required = false,
  multiple = true,
  fullWidth = true
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
      
      <MUIToggleButtonGroup
        value={value}
        onChange={(_, newValue) => onChange(newValue || [])}
        aria-label={title}
        color="primary"
        fullWidth={fullWidth}
        sx={{ 
          display: 'flex',
          width: '100%',
          '& .MuiToggleButton-root': {
            flex: 1,
            textAlign: 'center',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '72px'
          }
        }}
      >
        {options.map((option) => (
          <ToggleButton 
            key={option.value} 
            value={option.value}
            disabled={option.disabled}
          >
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                {option.label}
              </Typography>
              {option.description && (
                <Typography variant="caption" color="text.secondary" display="block">
                  {option.description}
                </Typography>
              )}
            </Box>
          </ToggleButton>
        ))}
      </MUIToggleButtonGroup>
      
      {error && (
        <FormHelperText error sx={{ mt: 1 }}>
          {error}
        </FormHelperText>
      )}
    </Box>
  );
};