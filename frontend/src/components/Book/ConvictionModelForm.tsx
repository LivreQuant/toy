// src/components/Book/ConvictionModelForm.tsx
import React, { useState, useEffect } from 'react';
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
  ToggleButtonGroup,
  ToggleButton,
  Slider,
  InputAdornment
} from '@mui/material';
import { ConvictionModelConfig } from '../../types';

interface ConvictionModelFormProps {
  value: ConvictionModelConfig;
  onChange: (config: ConvictionModelConfig) => void;
}

// Time unit options for multi-horizon
const TIME_UNITS = ['m', 'h', 'd', 'w'];

const ConvictionModelForm: React.FC<ConvictionModelFormProps> = ({ value, onChange }) => {
  // Use local state to manage the form
  const [localConfig, setLocalConfig] = useState<ConvictionModelConfig>({
    ...value,
  });

  const [validationError, setValidationError] = useState<string | null>(null);

  // THIS IS WHERE THE NEW CODE GOES - Replace the existing useEffect
  useEffect(() => {
    // Map internal properties to the API-expected format
    const outputConfig = {
      portfolioApproach: localConfig.portfolioApproach,
      
      // For incremental approach
      incrementalConvictionMethod: localConfig.incrementalConvictionMethod,
      
      // For target approach
      targetConvictionMethod: localConfig.targetConvictionMethod,
      
      // Include other properties
      maxScore: localConfig.maxScore,
      horizons: localConfig.horizons
    };
    
    onChange(outputConfig);
  }, [localConfig, onChange]);

  const normalizeTimeHorizon = (horizon: string): string => {
    // Extract numeric value and unit
    const match = horizon.match(/^(\d+)([mhdw])$/);
    if (!match) return horizon; // Return unchanged if format is incorrect
    
    const [_, valueStr, unit] = match;
    let value = parseInt(valueStr);
    
    // Standardize to the largest appropriate unit
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
    
    // If no standardization needed, return original
    return horizon;
  };

  const isDuplicateHorizon = (newHorizon: string, existingHorizons: string[]): boolean => {
    // Convert all horizons to minutes for comparison
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
    
    const newMinutes = getMinutes(newHorizon);
    
    // Check if any existing horizon converts to the same number of minutes
    return existingHorizons.some(horizon => getMinutes(horizon) === newMinutes);
  };

  const handleChange = (field: keyof ConvictionModelConfig, newValue: any) => {
    setLocalConfig(prev => ({ ...prev, [field]: newValue }));
  };

  // Add a new time horizon
  const handleAddHorizon = (horizonInput: string) => {
    if (!horizonInput.trim()) return;
    
    // Validate format: number + valid unit (m, h, d, w)
    const isValidFormat = /^\d+[mhdw]$/.test(horizonInput);
    if (!isValidFormat) {
        setValidationError("Invalid format. Use format like '30m', '1h', '1d'");
        return;
    }
    
    // Normalize the horizon to standardized form
    const normalizedHorizon = normalizeTimeHorizon(horizonInput);
    
    const newHorizons = [...(localConfig.horizons || [])];
    
    // Check if this horizon already exists in equivalent form
    if (isDuplicateHorizon(normalizedHorizon, newHorizons)) {
        setValidationError(`Time horizon ${normalizedHorizon} already exists in equivalent form`);
        return;
    }
    
    // Add and sort horizons by their time value
    newHorizons.push(normalizedHorizon);
    
    // Sort horizons by converting to minutes
    newHorizons.sort((a, b) => {
      const getMinutes = (horizon: string) => {
        const value = parseInt(horizon.match(/\d+/)?.[0] || '0');
        const unit = horizon.slice(-1);
        
        switch(unit) {
          case 'm': return value;
          case 'h': return value * 60;
          case 'd': return value * 60 * 24;
          case 'w': return value * 60 * 24 * 7;
          default: return 0;
        }
      };
      
    // Clear error when successful
    setValidationError(null);

      return getMinutes(a) - getMinutes(b);
    });
    
    setLocalConfig(prev => ({ ...prev, horizons: newHorizons }));
  };

    // Modify the getSampleColumns function
    const getSampleColumns = (): string[] => {
        const columns: string[] = ['instrumentId'];
        
        // For Target Portfolio, we don't need trade direction columns
        if (localConfig.portfolioApproach === 'target') {
        // Include target percentage or notional amount
        if (localConfig.targetConvictionMethod === 'percent') {
            columns.push('targetPercent');
        } else {
            columns.push('targetNotional');
        }
        } else {
        // For Incremental Trades, include the trading columns
        if (localConfig.incrementalConvictionMethod === 'side_score') {
            columns.push('side', 'score');
        } else if (localConfig.incrementalConvictionMethod === 'side_qty') {
            columns.push('side', 'quantity');
        } else if (localConfig.incrementalConvictionMethod === 'zscore') {
            columns.push('zscore');
        } else if (localConfig.incrementalConvictionMethod === 'multi-horizon') {
            const horizons = localConfig.horizons || ['1d', '5d', '20d'];
            
            // Use the time unit in the column name
            horizons.forEach(h => {
            // Extract numeric part and unit
            const match = h.match(/(\d+)([mhdw])/);
            if (match) {
                const [_, value, unit] = match;
                let unitText = unit;
                
                // Expand unit abbreviation
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
        
        // Always include these required fields
        columns.push('participationRate');
        columns.push('tag');
        columns.push('orderId');
        
        return columns;
    };
    
    // Modify the getSampleValues function similarly
    const getSampleValues = (): string[] => {
        const values: string[] = ['AAPL.US'];
        
        // For Target Portfolio, show target values without trade direction
        if (localConfig.portfolioApproach === 'target') {
        // Include target percentage or notional amount
        if (localConfig.targetConvictionMethod === 'percent') {
            values.push('2.5');
        } else {
            values.push('250000');
        }
        } else {
        // For Incremental Trades
        if (localConfig.incrementalConvictionMethod === 'side_score') {
            values.push('BUY', Math.floor(Math.random() * (localConfig.maxScore || 5) + 1).toString());
        } else if (localConfig.incrementalConvictionMethod === 'side_qty') {
            values.push('BUY', '100');
        } else if (localConfig.incrementalConvictionMethod === 'zscore') {
            values.push((Math.random() * 4 - 2).toFixed(2));
        } else if (localConfig.incrementalConvictionMethod === 'multi-horizon') {
            const horizons = localConfig.horizons || ['1d', '5d', '20d'];
            horizons.forEach(() => {
            values.push((Math.random() * 4 - 2).toFixed(2));
            });
        }
        }
        
        // Always include these required fields
        values.push('MEDIUM');
        values.push('value');
        values.push('order-001');
        
        return values;
    };

  return (
    <Box>
      {/* Order Format Preview */}
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
            {/* Header row */}
            <Box sx={{ color: 'primary.main', mb: 1 }}>
              {getSampleColumns().join(',')}
            </Box>
            
            {/* Sample data row */}
            <Box>
              {getSampleValues().join(',')}
            </Box>
          </Box>
        </Paper>

        {/* Required Fields Info with detailed descriptions */}
        <Alert severity="info" sx={{ mb: 3 }}>
            <Typography variant="body2" gutterBottom>
                <strong>Required fields:</strong>
            </Typography>
            
            <Box component="ul" sx={{ mt: 1, pl: 2, mb: 0 }}>
                <Typography component="li" variant="body2">
                    <strong>instrumentId:</strong> See our master symbology list for avaliable IDs. Note these IDs are subject to change depending on corporate actions. 
                </Typography>
                
                <Typography component="li" variant="body2">
                    <strong>participationRate:</strong> Please use LOW, MEDIUM, or HIGH to emphasis your fill urgency. 
                </Typography>
                
                <Typography component="li" variant="body2">
                    <strong>tag:</strong> A self defined identifier for downstream analytical purposes such as attribution. Examples may include strategy_XYZ, hedge, rebalance, and etc.
                </Typography>
                
                <Typography component="li" variant="body2">
                    <strong>orderId:</strong> A self defined unique identifier (e.g., ord_YYYYMMDDHHMM_AAPL.US_BUY) to help you identify an order in the event you want to cancel it.
                </Typography>
            </Box>
        </Alert>
      </Box>

      <Divider sx={{ my: 3 }} />
      
      {/* Portfolio Approach Section - Now using ToggleButtonGroup */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          Portfolio Construction Approach
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          How do you want to capture your convictions?
        </Typography>
        
        <ToggleButtonGroup
          exclusive
          fullWidth
          color="primary"
          value={localConfig.portfolioApproach}
          onChange={(_, value) => value && handleChange('portfolioApproach', value)}
          sx={{ mb: 2 }}
        >
          <ToggleButton value="incremental">
            <Box sx={{ py: 1, textAlign: 'center' }}>
              <Typography variant="body1" fontWeight="medium">
                Incremental Trades
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Individual BUY/SELL decisions
              </Typography>
            </Box>
          </ToggleButton>
          
          <ToggleButton value="target">
            <Box sx={{ py: 1, textAlign: 'center' }}>
              <Typography variant="body1" fontWeight="medium">
                Target Portfolio
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Desired portfolio allocations
              </Typography>
            </Box>
          </ToggleButton>
        </ToggleButtonGroup>
        
      </Box>
      
      <Divider sx={{ my: 3 }} />
      
      {/* Target Portfolio additional settings */}
        {localConfig.portfolioApproach === 'target' && (
        <Box sx={{ mb: 4 }}>
            <Typography variant="h6" gutterBottom>
            Conviction Expression Method
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
            How will you express your conviction?
            </Typography>
            <Box sx={{ mt: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px dashed', borderColor: 'divider' }}>
            <Typography variant="body2" sx={{ mb: 2 }}>
                Specify how you want to express target convictions:
            </Typography>
            
            {/* Full-width ToggleButtonGroup for target unit selection */}
            <ToggleButtonGroup
                exclusive
                fullWidth
                value={localConfig.targetConvictionMethod || 'percent'}
                onChange={(_, value) => value && handleChange('targetConvictionMethod', value)}
                aria-label="Target Unit"
                color="primary"
                size="small"
                sx={{ mb: 2 }}
            >
                <ToggleButton value="percent">
                <Typography variant="body2">Percentage of AUM</Typography>
                </ToggleButton>
                <ToggleButton value="notional">
                <Typography variant="body2">Notional Amount</Typography>
                </ToggleButton>
            </ToggleButtonGroup>
            
            {/* Add explanatory text for target percentages */}
            <Alert severity="info" sx={{ mt: 2 }}>
                <Typography variant="body2">
                {localConfig.targetConvictionMethod === 'percent' ? (
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
        </Box>
        )}

      {/* Conviction Method Section */}
      {localConfig.portfolioApproach !== 'target' && (
        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" gutterBottom>
            Conviction Expression Method
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            How will traders express their conviction in orders?
          </Typography>
          
          <ToggleButtonGroup
            exclusive
            fullWidth
            color="primary"
            value={localConfig.incrementalConvictionMethod}
            onChange={(_, value) => value && handleChange('incrementalConvictionMethod', value)}
            sx={{ mb: 2 }}
          >
            <ToggleButton value="side_score">
              <Box sx={{ py: 1, textAlign: 'center' }}>
                <Typography variant="body1" fontWeight="medium">
                  Directional Score
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  BUY/SELL with Score
                </Typography>
              </Box>
            </ToggleButton>

            <ToggleButton value="side_qty">
              <Box sx={{ py: 1, textAlign: 'center' }}>
                <Typography variant="body1" fontWeight="medium">
                  Directional Side
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  BUY/SELL with Quantity
                </Typography>
              </Box>
            </ToggleButton>
            
            <ToggleButton value="zscore">
              <Box sx={{ py: 1, textAlign: 'center' }}>
                <Typography variant="body1" fontWeight="medium">
                  Z-Score
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Statistical Signal
                </Typography>
              </Box>
            </ToggleButton>
            
            <ToggleButton value="multi-horizon">
              <Box sx={{ py: 1, textAlign: 'center' }}>
                <Typography variant="body1" fontWeight="medium">
                  Multi-Horizon Z-Score
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Statistical Signals at Different Timeframes
                </Typography>
              </Box>
            </ToggleButton>
          </ToggleButtonGroup>
          
          {/* Conviction Method Details */}
          <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px dashed', borderColor: 'divider' }}>

            {localConfig.incrementalConvictionMethod === 'side_score' && (
              <Box>
                <Typography variant="body2" paragraph>
                  Traders specify convictions using BUY/SELL directions with explicit scores.
                  This approach is well-suited for discretionary traders who think in terms of
                  conviction scores.
                </Typography>

                {/* NEW: Maximum score selector */}
                <Typography variant="subtitle2" gutterBottom>Score range:</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 2, mb: 2 }}>
                    <Typography variant="body2">1 to</Typography>
                    <TextField
                        label="Maximum Conviction Score"
                        type="number"
                        size="small"
                        value={localConfig.maxScore || 5}
                        onChange={(e) => {
                        const value = parseInt(e.target.value);
                        if (!isNaN(value) && value > 1) {
                            handleChange('maxScore', value);
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

            {localConfig.incrementalConvictionMethod === 'side_qty' && (
              <Box>
                <Typography variant="body2" paragraph>
                  Specify orders using BUY/SELL directions with explicit quantities.
                  This approach is well-suited for discretionary traders who think in terms of
                  specific position sizes.
                </Typography>
              </Box>
            )}
            
            {localConfig.incrementalConvictionMethod === 'zscore' && (
              <Box>
                <Typography variant="body2" paragraph>
                  Provide statistical signals (Z-Scores). The sign reflects conviction direction and the magnitude reflects conviction strength.
                </Typography>
              </Box>
            )}
            
            {localConfig.incrementalConvictionMethod === 'multi-horizon' && (
              <Box>
                <Typography variant="body2" paragraph>
                  Provide signals for multiple horizons. 
                  This offers a more nuanced view of expected movements over different timeframes. 
                  The timeframes are defined over business days and open market hours only, excluding pre and post hours.
                </Typography>
                
                <Typography variant="subtitle2" gutterBottom>Time horizons:</Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                  {(localConfig.horizons || ['30m', '1h', '1d', '20d']).map((horizon, index) => (
                    <Chip 
                      key={index}
                      label={horizon}
                      onDelete={() => {
                        const newHorizons = [...(localConfig.horizons || ['30m', '1h', '1d', '20d'])];
                        newHorizons.splice(index, 1);
                        handleChange('horizons', newHorizons);
                      }}
                    />
                  ))}
                </Box>
                
                {/* NEW: Improved horizon input with time units */}
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 2 }}>
                    <TextField
                        label="Add time horizon"
                        size="small"
                        placeholder="e.g., 30m, 1h, 1d"
                        inputProps={{ id: 'horizon-input' }}
                        helperText="Format: number + unit (m=minute, h=hour, d=day)"
                        sx={{ width: '100%' }} // Set fixed width instead of 100%
                    />
                    <Button 
                        variant="contained" 
                        sx={{ 
                            height: 40, // Match the height of the small TextField
                            alignSelf: 'flex-start' // Align to top of flex container
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