// src/components/Book/ConvictionModelForm.tsx
import React, { useState } from 'react';
import {
  Box,
  Typography,
  Divider,
  TextField,
  Select,
  MenuItem,
  InputLabel,
  Chip,
  Paper,
  Button,
  Alert,
  FormControl,
  InputAdornment
} from '@mui/material';
import { ConvictionModelConfig } from '@trading-app/types-core';
import { FormToggleGroup } from '../Form';

interface ConvictionModelFormProps {
  value: ConvictionModelConfig;
  onChange: (config: ConvictionModelConfig) => void;
}

const ConvictionModelForm: React.FC<ConvictionModelFormProps> = ({ value, onChange }) => {
  const [validationError, setValidationError] = useState<string | null>(null);

  const normalizeTimeHorizon = (horizon: string): string => {
    const match = horizon.match(/^(\d+)([mhdw])$/);
    if (!match) return horizon;
    
    const [_, valueStr, unit] = match;
    let val = parseInt(valueStr);
    
    if (unit === 'm' && val >= 60) {
      const hours = Math.floor(val / 60);
      const remainingMinutes = val % 60;
      
      if (remainingMinutes === 0) {
        return hours === 24 ? '1d' : `${hours}h`;
      }
    } else if (unit === 'h' && val >= 24) {
      const days = Math.floor(val / 24);
      const remainingHours = val % 24;
      
      if (remainingHours === 0) {
        return `${days}d`;
      }
    }
    
    return horizon;
  };

  const isDuplicateHorizon = (newHorizon: string, existingHorizons: string[]): boolean => {
    const getMinutes = (horizon: string): number => {
      const match = horizon.match(/^(\d+)([mhdw])$/);
      if (!match) return 0;
      
      const [_, valueStr, unit] = match;
      const val = parseInt(valueStr);
      
      switch(unit) {
        case 'm': return val;
        case 'h': return val * 60;
        case 'd': return val * 60 * 24;
        case 'w': return val * 60 * 24 * 7;
        default: return 0;
      }
    };
    
    const newMinutes = getMinutes(newHorizon);
    
    return existingHorizons.some(horizon => getMinutes(horizon) === newMinutes);
  };

  const handleChange = (field: keyof ConvictionModelConfig, newValue: any) => {
    console.log(`handleChange called: ${field} = ${newValue}`);
    console.log('Current value:', value);
    const newConfig = {
      ...value,
      [field]: newValue
    };
    console.log('New config:', newConfig);
    onChange(newConfig);
  };

  const handleAddHorizon = (horizonInput: string) => {
    if (!horizonInput.trim()) return;
    
    const isValidFormat = /^\d+[mhdw]$/.test(horizonInput);
    if (!isValidFormat) {
        setValidationError("Invalid format. Use format like '30m', '1h', '1d'");
        return;
    }
    
    const normalizedHorizon = normalizeTimeHorizon(horizonInput);
    
    const newHorizons = [...(value.horizons || [])];
    
    if (isDuplicateHorizon(normalizedHorizon, newHorizons)) {
        setValidationError(`Time horizon ${normalizedHorizon} already exists in equivalent form`);
        return;
    }
    
    newHorizons.push(normalizedHorizon);
    
    newHorizons.sort((a, b) => {
      const getMinutes = (horizon: string) => {
        const val = parseInt(horizon.match(/\d+/)?.[0] || '0');
        const unit = horizon.slice(-1);
        
        switch(unit) {
          case 'm': return val;
          case 'h': return val * 60;
          case 'd': return val * 60 * 24;
          case 'w': return val * 60 * 24 * 7;
          default: return 0;
        }
      };
      
      return getMinutes(a) - getMinutes(b);
    });
    
    handleChange('horizons', newHorizons);
    setValidationError(null);
  };

  const getSampleColumns = (): string[] => {
    const columns: string[] = ['instrumentId'];
    
    if (value.portfolioApproach === 'target') {
      if (value.targetConvictionMethod === 'percent') {
        columns.push('targetPercent');
      } else {
        columns.push('targetNotional');
      }
    } else {
      if (value.incrementalConvictionMethod === 'side_score') {
        columns.push('side', 'score');
      } else if (value.incrementalConvictionMethod === 'side_qty') {
        columns.push('side', 'quantity');
      } else if (value.incrementalConvictionMethod === 'zscore') {
        columns.push('zscore');
      } else if (value.incrementalConvictionMethod === 'multi-horizon') {
        const horizons = value.horizons || ['1d', '5d', '20d'];
        
        horizons.forEach(h => {
          const match = h.match(/(\d+)([mhdw])/);
          if (match) {
            const [_, val, unit] = match;
            let unitText = unit;
            
            switch(unit) {
              case 'm': unitText = 'min'; break;
              case 'h': unitText = 'hour'; break;
              case 'd': unitText = 'day'; break;
            }
            
            columns.push(`z${val}${unitText}`);
          }
        });
      }
    }
    
    columns.push('participationRate', 'tag', 'convictionId');
    
    return columns;
  };
    
  const getSampleValues = (): string[] => {
    const values: string[] = ['AAPL.US'];
    
    if (value.portfolioApproach === 'target') {
      if (value.targetConvictionMethod === 'percent') {
        values.push('2.5');
      } else {
        values.push('250000');
      }
    } else {
      if (value.incrementalConvictionMethod === 'side_score') {
        values.push('BUY', Math.floor(Math.random() * (value.maxScore || 5) + 1).toString());
      } else if (value.incrementalConvictionMethod === 'side_qty') {
        values.push('BUY', '100');
      } else if (value.incrementalConvictionMethod === 'zscore') {
        values.push((Math.random() * 4 - 2).toFixed(2));
      } else if (value.incrementalConvictionMethod === 'multi-horizon') {
        const horizons = value.horizons || ['1d', '5d', '20d'];
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
      {/* Conviction Format Preview */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="h6" gutterBottom>
          Conviction Schema Configuration
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Define how your convictions will be structured and what information is required. 
          Based on these selections, you must submit convictions in this format:
        </Typography>
                      
        <Paper elevation={0} sx={{ 
          p: 2, 
          bgcolor: 'background.default', 
          border: '1px solid', 
          borderColor: 'divider',
          borderRadius: 1,
          marginBottom: 2
        }}>
          <Box sx={{ 
            fontFamily: 'monospace', 
            fontSize: '0.9rem',
            overflowX: 'auto',
            whiteSpace: 'nowrap'
          }}>
            <Box sx={{ color: 'primary.main', mb: 1 }}>
              {getSampleColumns().join(',')}
            </Box>
            
            <Box>
              {getSampleValues().join(',')}
            </Box>
          </Box>
        </Paper>

        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2" gutterBottom>
            <strong>Required fields:</strong>
          </Typography>
          
          <Box component="ul" sx={{ mt: 1, pl: 2, mb: 0 }}>
            <Typography component="li" variant="body2">
              <strong>instrumentId:</strong> See our master symbology list for available IDs. Note these IDs are subject to change depending on corporate actions. 
            </Typography>
            
            <Typography component="li" variant="body2">
              <strong>participationRate:</strong> Please use LOW, MEDIUM, or HIGH to emphasis your fill urgency. 
            </Typography>
            
            <Typography component="li" variant="body2">
              <strong>tag:</strong> A self defined identifier for downstream analytical purposes such as attribution. Examples may include strategy_XYZ, hedge, rebalance, and etc.
            </Typography>
            
            <Typography component="li" variant="body2">
              <strong>convictionId:</strong> A self defined unique identifier (e.g., ord_YYYYMMDDHHMM_AAPL.US_BUY) to help you identify an conviction in the event you want to cancel it.
            </Typography>
          </Box>
        </Alert>
      </Box>

      <Divider sx={{ my: 3 }} />
      
      {/* Portfolio Approach Section */}
      <Box sx={{ mb: 4 }}>
        <FormToggleGroup
          title="Portfolio Construction Approach"
          description="How do you want to capture your convictions?"
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
          value={[value.portfolioApproach]}
          onChange={(values) => {
            console.log('FormToggleGroup onChange called with:', values);
            
            // Find the newly selected value by comparing with current value
            const currentValue = value.portfolioApproach;
            const newValue = values.find(v => v !== currentValue);
            
            if (newValue) {
              console.log('Setting new value:', newValue);
              handleChange('portfolioApproach', newValue);
            }
          }}
        />
      </Box>
      
      <Divider sx={{ my: 3 }} />
      
      {/* Target Portfolio additional settings */}
      {value.portfolioApproach === 'target' && (
        <Box sx={{ mb: 4 }}>
          <FormToggleGroup
            title="Conviction Expression Method"
            description="How will you express your conviction?"
            options={[
              { value: 'percent', label: 'Percentage of AUM' },
              { value: 'notional', label: 'Notional Amount' }
            ]}
            value={[value.targetConvictionMethod || 'percent']}
            onChange={(values) => {
              console.log('Target method FormToggleGroup onChange called with:', values);
              
              // Find the newly selected value by comparing with current value
              const currentValue = value.targetConvictionMethod || 'percent';
              const newValue = values.find(v => v !== currentValue);
              
              if (newValue) {
                console.log('Setting new target method value:', newValue);
                handleChange('targetConvictionMethod', newValue);
              }
            }}
          />
          
          <Alert severity="info" sx={{ mt: 2 }}>
            <Typography variant="body2">
              {value.targetConvictionMethod === 'percent' ? (
                <>
                  <strong>Percentage targets:</strong> The sum of absolute percentages must add up to 1. 
                  Positive values indicate long positions, negative values indicate short positions. The magnitude indicates conviction strength.
                </>
              ) : (
                <>
                  <strong>Notional targets:</strong> Specify the amount for each position, amounts are scaled proportional to the available capital.
                  Positive values indicate long positions, negative values indicate short positions. The magnitude indicates conviction strength.
                </>
              )}
            </Typography>
          </Alert>
        </Box>
      )}

      {/* Conviction Method Section */}
      {value.portfolioApproach !== 'target' && (
        <Box sx={{ mb: 4 }}>
          <FormToggleGroup
            title="Conviction Expression Method"
            description="How will traders express their conviction in convictions?"
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
            value={[value.incrementalConvictionMethod || 'side_score']}
            onChange={(values) => {
              console.log('Incremental method FormToggleGroup onChange called with:', values);
              
              // Find the newly selected value by comparing with current value
              const currentValue = value.incrementalConvictionMethod || 'side_score';
              const newValue = values.find(v => v !== currentValue);
              
              if (newValue) {
                console.log('Setting new incremental method value:', newValue);
                handleChange('incrementalConvictionMethod', newValue);
              }
            }}
          />
          
          {/* Method-specific Details */}
          <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px dashed', borderColor: 'divider' }}>

            {value.incrementalConvictionMethod === 'side_score' && (
              <Box>
                <Typography variant="body2" paragraph>
                  Traders specify convictions using BUY/SELL directions with explicit scores.
                  This approach is well-suited for discretionary traders who think in terms of
                  conviction scores.
                </Typography>

                <Typography variant="subtitle2" gutterBottom>Score range:</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 2, mb: 2 }}>
                  <Typography variant="body2">1 to</Typography>
                  <TextField
                    label="Maximum Conviction Score"
                    type="number"
                    size="small"
                    value={value.maxScore || 5}
                    onChange={(e) => {
                      const val = parseInt(e.target.value);
                      if (!isNaN(val) && val > 1) {
                        handleChange('maxScore', val);
                      }
                    }}
                    inputProps={{ min: 1, max: 10 }}
                    sx={{ width: 400 }}
                  />
                </Box>

                <Alert severity="info" sx={{ mt: 2 }}>
                  <Typography variant="body2">
                    <strong>Scores:</strong> Lower scores indicate low conviction and high scores indicate high conviction.
                  </Typography>
                </Alert>
              </Box>
            )}

            {value.incrementalConvictionMethod === 'side_qty' && (
              <Box>
                <Typography variant="body2" paragraph>
                  Specify convictions using BUY/SELL directions with explicit quantities.
                  This approach is well-suited for discretionary traders who think in terms of
                  specific position sizes.
                </Typography>
              </Box>
            )}
            
            {value.incrementalConvictionMethod === 'zscore' && (
              <Box>
                <Typography variant="body2" paragraph>
                  Provide statistical signals (Z-Scores). The sign reflects conviction direction and the magnitude reflects conviction strength.
                </Typography>
              </Box>
            )}
            
            {value.incrementalConvictionMethod === 'multi-horizon' && (
              <Box>
                <Typography variant="body2" paragraph>
                  Provide signals for multiple horizons. 
                  This offers a more nuanced view of expected movements over different timeframes. 
                  The timeframes are defined over business days and open market hours only, excluding pre and post hours.
                </Typography>
                
                <Typography variant="subtitle2" gutterBottom>Time horizons:</Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                  {(value.horizons || ['30m', '1h', '1d', '20d']).map((horizon, index) => (
                    <Chip 
                      key={index}
                      label={horizon}
                      onDelete={() => {
                        const newHorizons = [...(value.horizons || ['30m', '1h', '1d', '20d'])];
                        newHorizons.splice(index, 1);
                        handleChange('horizons', newHorizons);
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
                    sx={{ 
                      height: 40,
                      alignSelf: 'flex-start'
                    }}
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
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default ConvictionModelForm;