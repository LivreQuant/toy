// src/components/Book/ConvictionModelForm.tsx (REFACTORED)
import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Alert,
  Paper,
  Button,
  TextField,
  Chip
} from '@mui/material';
import { 
  ToggleButtonGroup, 
  FormField, 
  SectionGrid 
} from '../Form';
import { useFormState, useFormValidation } from '../../hooks/forms';
import { validationRules } from '../../utils/forms';
import { ConvictionModelConfig } from '@trading-app/types-core';

interface ConvictionModelFormProps {
  value: ConvictionModelConfig;
  onChange: (config: ConvictionModelConfig) => void;
}

const ConvictionModelForm: React.FC<ConvictionModelFormProps> = ({ value, onChange }) => {
  const { formData, updateField } = useFormState({
    initialData: value,
    onDataChange: onChange
  });

  const [validationError, setValidationError] = useState<string | null>(null);

  const validateFingerprint = (fingerprint: string): boolean => {
    const fingerprintRegex = /^[A-Za-z0-9+/]+=*$/;
    return fingerprintRegex.test(fingerprint) && fingerprint.length >= 32;
  };

  const handleAddHorizon = (horizonInput: string) => {
    if (!horizonInput.trim()) return;
    
    const isValidFormat = /^\d+[mhdw]$/.test(horizonInput);
    if (!isValidFormat) {
      setValidationError("Invalid format. Use format like '30m', '1h', '1d'");
      return;
    }
    
    const normalizedHorizon = normalizeTimeHorizon(horizonInput);
    const newHorizons = [...(formData.horizons || [])];
    
    if (isDuplicateHorizon(normalizedHorizon, newHorizons)) {
      setValidationError(`Time horizon ${normalizedHorizon} already exists`);
      return;
    }
    
    newHorizons.push(normalizedHorizon);
    newHorizons.sort((a, b) => getMinutes(a) - getMinutes(b));
    
    updateField('horizons', newHorizons);
    setValidationError(null);
  };

  const normalizeTimeHorizon = (horizon: string): string => {
    const match = horizon.match(/^(\d+)([mhdw])$/);
    if (!match) return horizon;
    
    const [_, valueStr, unit] = match;
    let value = parseInt(valueStr);
    
    if (unit === 'm' && value >= 60) {
      const hours = Math.floor(value / 60);
      const remainingMinutes = value % 60;
      if (remainingMinutes === 0) {
        return hours === 24 ? '1d' : `${hours}h`;
      }
    } else if (unit === 'h' && value >= 24) {
      const days = Math.floor(value / 24);
      const remainingHours = value % 24;
      if (remainingHours === 0) {
        return `${days}d`;
      }
    }
    
    return horizon;
  };

  const isDuplicateHorizon = (newHorizon: string, existingHorizons: string[]): boolean => {
    const newMinutes = getMinutes(newHorizon);
    return existingHorizons.some(horizon => getMinutes(horizon) === newMinutes);
  };

  const getMinutes = (horizon: string): number => {
    const match = horizon.match(/^(\d+)([mhdw])$/);
    if (!match) return 0;
    
    const [_, valueStr, unit] = match;
    const value = parseInt(valueStr);
    
    switch(unit) {
      case 'm': return value;
      case 'h': return value * 60;
      case 'd': return value * 60 * 24;
      case 'w': return value * 60 * 24 * 7;
      default: return 0;
    }
  };

  const getSampleColumns = (): string[] => {
    const columns: string[] = ['instrumentId'];
    
    if (formData.portfolioApproach === 'target') {
      if (formData.targetConvictionMethod === 'percent') {
        columns.push('targetPercent');
      } else {
        columns.push('targetNotional');
      }
    } else {
      if (formData.incrementalConvictionMethod === 'side_score') {
        columns.push('side', 'score');
      } else if (formData.incrementalConvictionMethod === 'side_qty') {
        columns.push('side', 'quantity');
      } else if (formData.incrementalConvictionMethod === 'zscore') {
        columns.push('zscore');
      } else if (formData.incrementalConvictionMethod === 'multi-horizon') {
        const horizons = formData.horizons || ['1d', '5d', '20d'];
        horizons.forEach(h => {
          const match = h.match(/(\d+)([mhdw])/);
          if (match) {
            const [_, value, unit] = match;
            let unitText = unit;
            switch(unit) {
              case 'm': unitText = 'min'; break;
              case 'h': unitText = 'hour'; break;
              case 'd': unitText = 'day'; break;
            }
            columns.push(`z${value}${unitText}`);
          }
        });
      }
    }
    
    columns.push('participationRate', 'tag', 'convictionId');
    return columns;
  };

  const getSampleValues = (): string[] => {
    const values: string[] = ['AAPL.US'];
    
    if (formData.portfolioApproach === 'target') {
      if (formData.targetConvictionMethod === 'percent') {
        values.push('2.5');
      } else {
        values.push('250000');
      }
    } else {
      if (formData.incrementalConvictionMethod === 'side_score') {
        values.push('BUY', Math.floor(Math.random() * (formData.maxScore || 5) + 1).toString());
      } else if (formData.incrementalConvictionMethod === 'side_qty') {
        values.push('BUY', '100');
      } else if (formData.incrementalConvictionMethod === 'zscore') {
        values.push((Math.random() * 4 - 2).toFixed(2));
      } else if (formData.incrementalConvictionMethod === 'multi-horizon') {
        const horizons = formData.horizons || ['1d', '5d', '20d'];
        horizons.forEach(() => {
          values.push((Math.random() * 4 - 2).toFixed(2));
        });
      }
    }
    
    values.push('MEDIUM', 'value', 'conviction-001');
    return values;
  };

  return (
    <Box>
      {/* Schema Preview */}
      <SectionGrid title="Conviction Schema Configuration" description="Define how your convictions will be structured">
        <Paper 
          elevation={0} 
          sx={{ 
            p: 2, 
            bgcolor: 'background.default', 
            border: '1px solid', 
            borderColor: 'divider',
            borderRadius: 1,
            marginBottom: 2,
            fontFamily: 'monospace', 
            fontSize: '0.9rem',
            overflowX: 'auto',
            whiteSpace: 'nowrap'
          }}
        >
          <Box sx={{ color: 'primary.main', mb: 1 }}>
            {getSampleColumns().join(',')}
          </Box>
          <Box>
            {getSampleValues().join(',')}
          </Box>
        </Paper>

        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2" gutterBottom>
            <strong>Required fields:</strong>
          </Typography>
          <Box component="ul" sx={{ mt: 1, pl: 2, mb: 0 }}>
            <Typography component="li" variant="body2">
              <strong>instrumentId:</strong> See our master symbology list for available IDs
            </Typography>
            <Typography component="li" variant="body2">
              <strong>participationRate:</strong> Use LOW, MEDIUM, or HIGH for fill urgency
            </Typography>
            <Typography component="li" variant="body2">
              <strong>tag:</strong> Self-defined identifier for analytical purposes
            </Typography>
            <Typography component="li" variant="body2">
              <strong>convictionId:</strong> Unique identifier for tracking convictions
            </Typography>
          </Box>
        </Alert>
      </SectionGrid>

      {/* Portfolio Approach */}
      <SectionGrid title="Portfolio Construction Approach" description="How do you want to capture your convictions?">
        <ToggleButtonGroup
          title=""
          options={[
            { 
              value: 'incremental', 
              label: 'Incremental Trades',
              description: 'Individual BUY/SELL decisions'
            },
            { 
              value: 'target', 
              label: 'Target Portfolio',
              description: 'Desired portfolio allocations'
            }
          ]}
          value={[formData.portfolioApproach]}
          onChange={(value) => updateField('portfolioApproach', value[0] as "incremental" | "target")}
          multiple={false}
        />
      </SectionGrid>

      {/* Target Portfolio Method */}
      {formData.portfolioApproach === 'target' && (
        <SectionGrid title="Conviction Expression Method" description="How will you express your conviction?">
          <ToggleButtonGroup
            title=""
            options={[
              { value: 'percent', label: 'Percentage of AUM' },
              { value: 'notional', label: 'Notional Amount' }
            ]}
            value={[formData.targetConvictionMethod || 'percent']}
            onChange={(value) => updateField('targetConvictionMethod', value[0] as "percent" | "notional")}
            multiple={false}
          />
          
          <Alert severity="info" sx={{ mt: 2 }}>
            <Typography variant="body2">
              {formData.targetConvictionMethod === 'percent' ? (
                <>
                  <strong>Percentage targets:</strong> The sum of absolute percentages must add up to 1. 
                  Positive values indicate long positions, negative values indicate short positions.
                </>
              ) : (
                <>
                  <strong>Notional targets:</strong> Specify the amount for each position, amounts are scaled proportional to available capital.
                  Positive values indicate long positions, negative values indicate short positions.
                </>
              )}
            </Typography>
          </Alert>
        </SectionGrid>
      )}

      {/* Incremental Method */}
      {formData.portfolioApproach !== 'target' && (
        <SectionGrid title="Conviction Expression Method" description="How will traders express their conviction?">
          <ToggleButtonGroup
            title=""
            options={[
              { 
                value: 'side_score', 
                label: 'Directional Score',
                description: 'BUY/SELL with Score'
              },
              { 
                value: 'side_qty', 
                label: 'Directional Side',
                description: 'BUY/SELL with Quantity'
              },
              { 
                value: 'zscore', 
                label: 'Z-Score',
                description: 'Statistical Signal'
              },
              { 
                value: 'multi-horizon', 
                label: 'Multi-Horizon Z-Score',
                description: 'Statistical Signals at Different Timeframes'
              }
            ]}
            value={[formData.incrementalConvictionMethod || 'side_score']} 
            onChange={(value) => updateField('incrementalConvictionMethod', value[0] as "side_score" | "side_qty" | "zscore" | "multi-horizon")}
            multiple={false}
          />

          {/* Method-specific configurations */}
          {formData.incrementalConvictionMethod === 'side_score' && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>Score range:</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 2, mb: 2 }}>
                <Typography variant="body2">1 to</Typography>
                <FormField
                  label="Maximum Conviction Score"
                  type="number"
                  value={formData.maxScore || 5}
                  onChange={(value) => updateField('maxScore', Number(value))}
                  fullWidth={false}
                />
              </Box>
              <Alert severity="info">
                <Typography variant="body2">
                  <strong>Scores:</strong> Lower scores indicate low conviction and high scores indicate high conviction.
                </Typography>
              </Alert>
            </Box>
          )}

          {formData.incrementalConvictionMethod === 'multi-horizon' && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>Time horizons:</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                {(formData.horizons || ['30m', '1h', '1d', '20d']).map((horizon, index) => (
                  <Chip 
                    key={index}
                    label={horizon}
                    onDelete={() => {
                      const newHorizons = [...(formData.horizons || ['30m', '1h', '1d', '20d'])];
                      newHorizons.splice(index, 1);
                      updateField('horizons', newHorizons);
                    }}
                  />
                ))}
              </Box>
              
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2 }}>
                <TextField
                  label="Add time horizon"
                  size="small"
                  placeholder="e.g., 30m, 1h, 1d"
                  inputProps={{ id: 'horizon-input' }}
                  helperText="Format: number + unit (m=minute, h=hour, d=day)"
                  sx={{ width: '100%' }}
                />
                <Button 
                  variant="contained" 
                  sx={{ height: 40, alignSelf: 'flex-start' }}
                  onClick={() => {
                    const input = document.getElementById('horizon-input') as HTMLInputElement;
                    if (input) {
                      handleAddHorizon(input.value);
                      input.value = '';
                    }
                  }}
                >
                  Add
                </Button>
              </Box>
              
              {validationError && (
                <Typography color="error" variant="caption">
                  {validationError}
                </Typography>
              )}
            </Box>
          )}
        </SectionGrid>
      )}
    </Box>
  );
};

export default ConvictionModelForm;