// src/components/Form/FormFields/ToggleButtonGroup.tsx (add interface export)
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
        orientation={fullWidth ? 'horizontal' : 'vertical'}
        fullWidth={fullWidth}
        sx={{ 
          flexWrap: 'wrap',
          '& .MuiToggleButton-root': {
            flex: fullWidth ? '1 1 auto' : 'none',
            textAlign: 'center'
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
              <Typography variant="body2">{option.label}</Typography>
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
        <FormHelperText error>{error}</FormHelperText>
      )}
    </Box>
  );
};