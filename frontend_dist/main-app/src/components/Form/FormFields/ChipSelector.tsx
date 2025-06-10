// src/components/Form/FormFields/ChipSelector.tsx (add interface export)
import React from 'react';
import {
  Box,
  Chip,
  Typography,
  FormHelperText,
  Paper
} from '@mui/material';

interface ChipOption {
  value: string;
  label: string;
  color?: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning';
  disabled?: boolean;
}

export interface ChipSelectorProps {
  title: string;
  description?: string;
  options: ChipOption[];
  value: string[];
  onChange: (value: string[]) => void;
  error?: string;
  required?: boolean;
  multiple?: boolean;
  maxSelection?: number;
  variant?: 'filled' | 'outlined';
}

export const ChipSelector: React.FC<ChipSelectorProps> = ({
  title,
  description,
  options,
  value,
  onChange,
  error,
  required = false,
  multiple = true,
  maxSelection,
  variant = 'filled'
}) => {
  const handleChipClick = (optionValue: string) => {
    if (multiple) {
      const newValue = value.includes(optionValue)
        ? value.filter(v => v !== optionValue)
        : maxSelection && value.length >= maxSelection
          ? value
          : [...value, optionValue];
      onChange(newValue);
    } else {
      onChange(value.includes(optionValue) ? [] : [optionValue]);
    }
  };

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
      
      <Paper 
        variant="outlined" 
        sx={{ 
          p: 2, 
          minHeight: 60,
          display: 'flex',
          flexWrap: 'wrap',
          gap: 1,
          alignItems: 'flex-start'
        }}
      >
        {options.map((option) => (
          <Chip
            key={option.value}
            label={option.label}
            onClick={() => !option.disabled && handleChipClick(option.value)}
            color={value.includes(option.value) ? (option.color || 'primary') : 'default'}
            variant={value.includes(option.value) ? variant : 'outlined'}
            disabled={option.disabled}
            clickable
            sx={{
              transition: 'all 0.2s ease',
              '&:hover': {
                transform: option.disabled ? 'none' : 'scale(1.05)'
              }
            }}
          />
        ))}
      </Paper>
      
      {maxSelection && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
          {value.length}/{maxSelection} selected
        </Typography>
      )}
      
      {error && (
        <FormHelperText error sx={{ mt: 0.5 }}>
          {error}
        </FormHelperText>
      )}
    </Box>
  );
};