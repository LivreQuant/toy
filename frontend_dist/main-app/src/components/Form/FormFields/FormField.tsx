// src/components/Form/FormFields/FormField.tsx (add interface export)
import React from 'react';
import {
  TextField,
  FormControl,
  FormLabel,
  FormHelperText,
  Box,
  Typography
} from '@mui/material';

export interface FormFieldProps {
  label: string;
  value: string | number;
  onChange: (value: string | number) => void;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  type?: 'text' | 'email' | 'password' | 'number' | 'tel' | 'url';
  placeholder?: string;
  helperText?: string;
  multiline?: boolean;
  rows?: number;
  maxLength?: number;
  fullWidth?: boolean;
  size?: 'small' | 'medium';
  variant?: 'outlined' | 'filled' | 'standard';
}

export const FormField: React.FC<FormFieldProps> = ({
  label,
  value,
  onChange,
  error,
  required = false,
  disabled = false,
  type = 'text',
  placeholder,
  helperText,
  multiline = false,
  rows = 4,
  maxLength,
  fullWidth = true,
  size = 'medium',
  variant = 'outlined'
}) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = type === 'number' ? Number(e.target.value) : e.target.value;
    onChange(newValue);
  };

  return (
    <FormControl fullWidth={fullWidth} error={!!error}>
      <TextField
        label={label}
        value={value}
        onChange={handleChange}
        error={!!error}
        required={required}
        disabled={disabled}
        type={type}
        placeholder={placeholder}
        multiline={multiline}
        rows={multiline ? rows : undefined}
        size={size}
        variant={variant}
        inputProps={{
          maxLength: maxLength
        }}
      />
      
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
        <FormHelperText>
          {error || helperText}
        </FormHelperText>
        
        {maxLength && (
          <Typography variant="caption" color="text.secondary">
            {String(value).length}/{maxLength}
          </Typography>
        )}
      </Box>
    </FormControl>
  );
};