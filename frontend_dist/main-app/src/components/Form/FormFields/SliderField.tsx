// src/components/Form/FormFields/SliderField.tsx (add interface export)
import React from 'react';
import {
  Box,
  Slider,
  Typography,
  FormControl,
  FormHelperText,
  Input,
  InputAdornment
} from '@mui/material';
import { styled } from '@mui/material/styles';

interface SliderMark {
  value: number;
  label: string;
}

export interface SliderFieldProps {
  title: string;
  description?: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  marks?: SliderMark[];
  error?: string;
  required?: boolean;
  disabled?: boolean;
  showInput?: boolean;
  unit?: string;
  formatValue?: (value: number) => string;
  color?: 'primary' | 'secondary';
}

const StyledSlider = styled(Slider)(({ theme }) => ({
  '& .MuiSlider-markLabel[data-index="0"]': {
    transform: 'translateX(0%)',
    left: '0%',
  },
  '& .MuiSlider-markLabel[data-index="1"]': {
    transform: 'translateX(0%)',
    left: '50%',
  },
  '& .MuiSlider-markLabel[data-index="2"]': {
    transform: 'translateX(-50%)',
    left: '100%',
  },
  '& .MuiSlider-markLabel[data-index="3"]': {
    transform: 'translateX(-100%)',
    left: '100%',
  },
}));

export const SliderField: React.FC<SliderFieldProps> = ({
  title,
  description,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  marks,
  error,
  required = false,
  disabled = false,
  showInput = false,
  unit,
  formatValue,
  color = 'primary'
}) => {
  const handleSliderChange = (_: Event, newValue: number | number[]) => {
    onChange(Array.isArray(newValue) ? newValue[0] : newValue);
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = event.target.value === '' ? min : Number(event.target.value);
    onChange(newValue);
  };

  const displayValue = formatValue ? formatValue(value) : value;

  return (
    <FormControl fullWidth error={!!error} sx={{ mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        {title} {required && <span style={{ color: 'red' }}>*</span>}
      </Typography>
      
      {description && (
        <Typography variant="body2" color="text.secondary" paragraph>
          {description}
        </Typography>
      )}
      
      <Box sx={{ px: 1 }}>
        <StyledSlider
          value={value}
          onChange={handleSliderChange}
          min={min}
          max={max}
          step={step}
          marks={marks}
          disabled={disabled}
          color={color}
          valueLabelDisplay="auto"
          valueLabelFormat={formatValue || ((val) => `${val}${unit || ''}`)}
        />
      </Box>
      
      {showInput && (
        <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="body2">Current value:</Typography>
          <Input
            value={value}
            onChange={handleInputChange}
            disabled={disabled}
            inputProps={{
              min,
              max,
              type: 'number',
              step
            }}
            endAdornment={unit && <InputAdornment position="end">{unit}</InputAdornment>}
            sx={{ width: 120 }}
          />
        </Box>
      )}
      
      {error && (
        <FormHelperText>{error}</FormHelperText>
      )}
    </FormControl>
  );
};