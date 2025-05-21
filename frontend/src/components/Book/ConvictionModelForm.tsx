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
  Alert,
  FormControl,
  ToggleButtonGroup,
  ToggleButton
} from '@mui/material';

// Unified order schema / conviction model configuration
export interface ConvictionModelConfig {
  // Portfolio approach
  portfolioApproach: 'incremental' | 'target';
  
  // Additional parameters - always included
  targetPortfolioUnit?: 'percent' | 'notional';

  // Core conviction method
  convictionMethod?: 'side_score' | 'side_qty' | 'zscore' | 'multi-horizon';
  
  // Configuration parameters
  scoreRange?: [number, number]; // For side with score
  horizons?: string[]; // For multi-horizon approach
  
}

interface ConvictionModelFormProps {
  value: ConvictionModelConfig;
  onChange: (config: ConvictionModelConfig) => void;
}

const ConvictionModelForm: React.FC<ConvictionModelFormProps> = ({ value, onChange }) => {
  // Use local state to manage the form
  const [localConfig, setLocalConfig] = useState<ConvictionModelConfig>({
    ...value,
  });

  // Update the parent component when local config changes
  useEffect(() => {
    onChange({
      ...localConfig,
    });
  }, [localConfig, onChange]);

  const handleChange = (field: keyof ConvictionModelConfig, newValue: any) => {
    setLocalConfig(prev => ({ ...prev, [field]: newValue }));
  };

  // Generate sample columns based on conviction method
  const getSampleColumns = (): string[] => {
    const columns: string[] = ['instrumentId'];
    
    if (localConfig.convictionMethod === 'side_score') {
        columns.push('side', 'score');
    } else if (localConfig.convictionMethod === 'side_qty') {
        columns.push('side', 'quantity');
    } else if (localConfig.convictionMethod === 'zscore') {
      columns.push('zscore');
    } else if (localConfig.convictionMethod === 'multi-horizon') {
      const horizons = localConfig.horizons || [1, 5, 20];
      horizons.forEach(h => columns.push(`z${h}d`));
    }
    
    if (localConfig.portfolioApproach === 'target') {
      if (localConfig.targetPortfolioUnit === 'percent') {
        columns.push('targetPercent');
      } else {
        columns.push('targetNotional');
      }
    }
    
    // Always include these required fields
    columns.push('participationRate');
    columns.push('category');
    columns.push('orderId');
    
    return columns;
  };

  // Generate sample data row based on conviction method
  const getSampleValues = (): string[] => {
    const values: string[] = ['AAPL.US'];
    
    if (localConfig.convictionMethod === 'side_score') {
      values.push('BUY', '2');
    } else if (localConfig.convictionMethod === 'side_qty') {
      values.push('BUY', '100');
    } else if (localConfig.convictionMethod === 'zscore') {
      values.push('2.1');
    } else if (localConfig.convictionMethod === 'multi-horizon') {
      const horizons = localConfig.horizons || [1, 5, 20];
      horizons.forEach(() => {
        values.push((Math.random() * 4 - 2).toFixed(2));
      });
    }
    
    if (localConfig.portfolioApproach === 'target') {
      if (localConfig.targetPortfolioUnit === 'percent') {
        values.push('2.5');
      } else {
        values.push('250000');
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
            Based on your selections, traders will submit orders in this format:
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

        {/* Required Fields Info */}
        <Alert severity="info" sx={{ mb: 3 }}>
            <Typography variant="body2">
            <strong>Required fields:</strong> instrumentId, participationRate, category, orderId
            </Typography>
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
            How will you express you conviction?
            </Typography>
            <Box sx={{ mt: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px dashed', borderColor: 'divider' }}>
            <Typography variant="body2" sx={{ mb: 2 }}>
                Specify how you want to express target convictions:
            </Typography>
            <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel>Target Unit</InputLabel>
                <Select
                value={localConfig.targetPortfolioUnit || 'percent'}
                onChange={(e) => handleChange('targetPortfolioUnit', e.target.value)}
                label="Target Unit"
                >
                <MenuItem value="percent">Percentage (%) of AUM</MenuItem>
                <MenuItem value="notional">Notional ($ amount)</MenuItem>
                </Select>
            </FormControl>
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
            value={localConfig.convictionMethod}
            onChange={(_, value) => value && handleChange('convictionMethod', value)}
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
            
            <ToggleButton value="multi-zscore">
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

                {localConfig.convictionMethod === 'side_score' && (
                    <Box>
                    <Typography variant="body2" paragraph>
                        Traders specify convictions using BUY/SELL directions with explicit scores.
                        This approach is well-suited for discretionary traders who think in terms of
                        conviction scores.
                    </Typography>

                    <Typography variant="subtitle2" gutterBottom>Score magnitude:</Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                        {(localConfig.horizons || [1, 5, 20]).map((days, index) => (
                        <Chip 
                            key={index}
                            label={`${days} day${days !== 1 ? 's' : ''}`}
                            onDelete={() => {
                            const newHorizons = [...(localConfig.horizons || [1, 5, 20])];
                            newHorizons.splice(index, 1);
                            handleChange('horizons', newHorizons);
                            }}
                        />
                        ))}
                    </Box>
                    
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                        <TextField
                        label="Add horizon (days)"
                        type="number"
                        size="small"
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                            const input = e.target as HTMLInputElement;
                            const value = parseInt(input.value);
                            if (value > 0) {
                                handleChange('horizons', [...(localConfig.horizons || [1, 5, 20]), value]);
                                input.value = '';
                            }
                            }
                        }}
                        sx={{ width: 150 }}
                        inputProps={{ min: 1 }}
                        />
                        <Typography variant="caption" color="text.secondary">
                        Press Enter to add
                        </Typography>
                    </Box>

                    <Typography variant="subtitle2">Example:</Typography>
                    <Box sx={{ fontFamily: 'monospace', bgcolor: 'action.hover', p: 1, borderRadius: 1, mt: 1 }}>
                        AAPL.US, BUY, 1, HIGH, value, order-001
                    </Box>
                    </Box>
                )}

                {localConfig.convictionMethod === 'side_qty' && (
                    <Box>
                    <Typography variant="body2" paragraph>
                        Traders specify orders using BUY/SELL directions with explicit quantities.
                        This approach is well-suited for discretionary traders who think in terms of
                        specific position sizes.
                    </Typography>
                    <Typography variant="subtitle2">Example:</Typography>
                    <Box sx={{ fontFamily: 'monospace', bgcolor: 'action.hover', p: 1, borderRadius: 1, mt: 1 }}>
                        AAPL.US, BUY, 1000, HIGH, value, order-001
                    </Box>
                    </Box>
                )}
                
                {localConfig.convictionMethod === 'zscore' && (
                    <Box>
                    <Typography variant="body2" paragraph>
                        Traders provide statistical signals (Z-Scores) where positive values indicate 
                        long positions and negative values indicate short positions. The magnitude 
                        reflects conviction strength.
                    </Typography>
                                    
                    <Typography variant="subtitle2">Example:</Typography>
                    <Box sx={{ fontFamily: 'monospace', bgcolor: 'action.hover', p: 1, borderRadius: 1, mt: 1 }}>
                        AAPL.US, 2.1, MEDIUM, momentum, order-001
                    </Box>
                    </Box>
                )}
                
                {localConfig.convictionMethod === 'multi-horizon' && (
                    <Box>
                    <Typography variant="body2" paragraph>
                        Traders provide signals for multiple time horizons, offering a more 
                        nuanced view of expected price movements over different timeframes.
                    </Typography>
                    
                    <Typography variant="subtitle2" gutterBottom>Time horizons in days:</Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                        {(localConfig.horizons || [1, 5, 20]).map((days, index) => (
                        <Chip 
                            key={index}
                            label={`${days} day${days !== 1 ? 's' : ''}`}
                            onDelete={() => {
                            const newHorizons = [...(localConfig.horizons || [1, 5, 20])];
                            newHorizons.splice(index, 1);
                            handleChange('horizons', newHorizons);
                            }}
                        />
                        ))}
                    </Box>
                    
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                        <TextField
                        label="Add horizon (days)"
                        type="number"
                        size="small"
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                            const input = e.target as HTMLInputElement;
                            const value = parseInt(input.value);
                            if (value > 0) {
                                handleChange('horizons', [...(localConfig.horizons || [1, 5, 20]), value]);
                                input.value = '';
                            }
                            }
                        }}
                        sx={{ width: 150 }}
                        inputProps={{ min: 1 }}
                        />
                        <Typography variant="caption" color="text.secondary">
                        Press Enter to add
                        </Typography>
                    </Box>
                    
                    <Typography variant="subtitle2">Example:</Typography>
                    <Box sx={{ fontFamily: 'monospace', bgcolor: 'action.hover', p: 1, borderRadius: 1, mt: 1 }}>
                        AAPL.US, 1.2, 0.8, -0.5, MEDIUM, mean-reversion, order-001
                    </Box>
                    </Box>
                )}
            </Box>
        </Box>
        )}
    </Box>
  );
};

export default ConvictionModelForm;