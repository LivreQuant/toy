// src/components/Book/BaseBookForm2.tsx (COMPLETE FIXED VERSION)
import React from 'react';
import { 
  TextField, 
  Grid, 
  Box, 
  Typography, 
  ToggleButton,
  ToggleButtonGroup,
  Slider,
  FormControl,
  FormHelperText
} from '@mui/material';
import { styled } from '@mui/material/styles';
import { 
  FormWizard, 
  FormContainer
} from '../Form';
import { useFormState, useFormValidation } from '../../hooks/forms';
import { validationRules, combineValidators } from '../../utils/forms';
import { BookRequest, ConvictionModelConfig } from '@trading-app/types-core';
import ConvictionModelForm from './ConvictionModelForm2';

// StyledSlider component from original
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

interface BaseBookFormProps {
  isEditMode: boolean;
  initialData?: Partial<BookRequest>;
  onSubmit: (formData: BookRequest) => Promise<{ success: boolean; bookId?: string; error?: string }>;
  submitButtonText: string;
  title: string;
  subtitle: string;
}

const sectors = [
  { value: 'generalist', label: 'Generalist', examples: 'All sectors' },
  { value: 'tech', label: 'Technology' },
  { value: 'healthcare', label: 'Healthcare' },
  { value: 'financials', label: 'Financials' },
  { value: 'consumer', label: 'Consumer' },
  { value: 'industrials', label: 'Industrials' },
  { value: 'energy', label: 'Energy' },
  { value: 'materials', label: 'Materials' },
  { value: 'utilities', label: 'Utilities' },
  { value: 'realestate', label: 'Real Estate' }
];

const actualSectorIds = sectors
  .filter(sector => sector.value !== 'generalist')
  .map(sector => sector.value);

// Create properly typed default conviction schema
const createDefaultConvictionSchema = (): ConvictionModelConfig => ({
  portfolioApproach: 'incremental' as const,
  targetConvictionMethod: 'percent' as const,
  incrementalConvictionMethod: 'side_score' as const,
  maxScore: 3,
  horizons: ['30m', '1h', '1d'],
});

export const BaseBookForm: React.FC<BaseBookFormProps> = ({
  isEditMode,
  initialData = {},
  onSubmit,
  submitButtonText,
  title,
  subtitle
}) => {
  // Ensure conviction schema is properly typed
  const defaultConvictionSchema = initialData.convictionSchema || createDefaultConvictionSchema();
  
  const { formData, updateField } = useFormState({
    initialData: {
      name: initialData.name || 'My Trading Book',
      regions: initialData.regions || ['us'],
      markets: initialData.markets || ['equities'],
      instruments: initialData.instruments || ['stocks'],
      investmentApproaches: initialData.investmentApproaches || [],
      investmentTimeframes: initialData.investmentTimeframes || [],
      sectors: initialData.sectors || [],
      positionTypes: {
        long: initialData.positionTypes?.long || false,
        short: initialData.positionTypes?.short || false
      },
      initialCapital: initialData.initialCapital || 100000000,
      convictionSchema: defaultConvictionSchema
    },
    autoSave: true,
    storageKey: isEditMode ? undefined : 'book-form-draft'
  });

  const { errors, validateForm } = useFormValidation({
    initialData: formData,
    validationRules: [
      {
        field: 'name',
        validate: combineValidators(
          validationRules.required('Book name is required'),
          validationRules.minLength(2, 'Book name must be at least 2 characters')
        ),
        message: 'Book name validation failed'
      },
      {
        field: 'regions',
        validate: validationRules.arrayMinLength(1, 'At least one region must be selected'),
        message: 'Region selection validation failed'
      },
      {
        field: 'markets',
        validate: validationRules.arrayMinLength(1, 'At least one market must be selected'),
        message: 'Market selection validation failed'
      },
      {
        field: 'instruments',
        validate: validationRules.arrayMinLength(1, 'At least one instrument must be selected'),
        message: 'Instrument selection validation failed'
      },
      {
        field: 'investmentApproaches',
        validate: validationRules.arrayMinLength(1, 'Please select at least one investment approach'),
        message: 'Investment approach validation failed'
      },
      {
        field: 'investmentTimeframes',
        validate: validationRules.arrayMinLength(1, 'Please select at least one investment timeframe'),
        message: 'Investment timeframe validation failed'
      },
      {
        field: 'sectors',
        validate: validationRules.arrayMinLength(1, 'Please select at least one sector'),
        message: 'Sector validation failed'
      },
      {
        field: 'initialCapital',
        validate: combineValidators(
          validationRules.required('Initial capital is required'),
          validationRules.min(1000000, 'Minimum capital is $1M')
        ),
        message: 'Initial capital validation failed'
      }
    ]
  });

  // Event handlers with proper typing
  const handleRegionChange = (event: React.MouseEvent<HTMLElement>, value: string[]) => {
    updateField('regions', value || []);
  };

  const handleMarketChange = (event: React.MouseEvent<HTMLElement>, value: string[]) => {
    updateField('markets', value || []);
  };

  const handleInstrumentChange = (event: React.MouseEvent<HTMLElement>, value: string[]) => {
    updateField('instruments', value || []);
  };

  const handleInvestmentApproachChange = (event: React.MouseEvent<HTMLElement>, value: string[]) => {
    updateField('investmentApproaches', value || []);
  };

  const handleTimeframeChange = (event: React.MouseEvent<HTMLElement>, value: string[]) => {
    updateField('investmentTimeframes', value || []);
  };

  const handlePositionTypeChange = (event: React.MouseEvent<HTMLElement>, value: string[]) => {
    updateField('positionTypes', {
      long: value.includes('long'),
      short: value.includes('short')
    });
  };

  // Sector selection handler from original
  const handleSectorSelectionChange = (newValue: string[]) => {
    const hasGeneralistBefore = formData.sectors.includes('generalist');
    const hasGeneralistAfter = newValue.includes('generalist');
    
    if (hasGeneralistBefore !== hasGeneralistAfter) {
      if (hasGeneralistAfter) {
        updateField('sectors', ['generalist', ...actualSectorIds]);
      } else {
        updateField('sectors', formData.sectors.filter(id => id !== 'generalist'));
      }
      return;
    }
    
    if (hasGeneralistBefore && 
        hasGeneralistAfter && 
        newValue.length < formData.sectors.length) {
      const sectorBeingRemoved = formData.sectors.find(id => !newValue.includes(id) && id !== 'generalist');
      if (sectorBeingRemoved) {
        updateField('sectors', formData.sectors.filter(id => id !== 'generalist' && id !== sectorBeingRemoved));
      }
      return;
    }
    
    const allSectorsSelected = actualSectorIds.every(sector => 
      newValue.includes(sector)
    );
    
    if (allSectorsSelected && !hasGeneralistAfter) {
      updateField('sectors', [...newValue, 'generalist']);
    } else {
      updateField('sectors', newValue);
    }
  };

  const steps = [
    {
      label: 'Basic Information',
      content: (
        <Grid container spacing={3}>
          <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
            <TextField
              fullWidth
              label="Book Name"
              name="name"
              value={formData.name}
              onChange={(e) => updateField('name', e.target.value)}
              error={!!errors.name}
              helperText={errors.name}
              required
            />
          </Grid>
          
          <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
            <Typography variant="h6" gutterBottom>
              Region
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Geographic focus of the investment strategy
            </Typography>
            
            <ToggleButtonGroup
              value={formData.regions}
              onChange={handleRegionChange}
              aria-label="Regions"
              color="primary"
              fullWidth
            >
              <ToggleButton value="us">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">US Region</Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="eu">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">EU Region</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Coming soon
                  </Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="asia">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Asia Region</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Coming soon
                  </Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="emerging">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Emerging</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Coming soon
                  </Typography>
                </Box>
              </ToggleButton>
            </ToggleButtonGroup>
            {errors.regions && (
              <Typography color="error" variant="caption">{errors.regions}</Typography>
            )}
          </Grid>
          
          <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
            <Typography variant="h6" gutterBottom>
              Markets
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              The markets accessed by the investment strategy
            </Typography>
            
            <ToggleButtonGroup
              value={formData.markets}
              onChange={handleMarketChange}
              aria-label="Markets"
              color="primary"
              fullWidth
            >
              <ToggleButton value="equities">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Equities</Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="bonds">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Bonds</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Coming soon
                  </Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="currencies" disabled>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Currencies</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Coming soon
                  </Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="commodities" disabled>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Commodities</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Coming soon
                  </Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="cryptos" disabled>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Cryptos</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Coming soon
                  </Typography>
                </Box>
              </ToggleButton>
            </ToggleButtonGroup>
            {errors.markets && (
              <Typography color="error" variant="caption">{errors.markets}</Typography>
            )}
          </Grid>
          
          <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
            <Typography variant="h6" gutterBottom>
              Instruments
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Financial instruments used in the portfolio
            </Typography>
            
            <ToggleButtonGroup
              value={formData.instruments}
              onChange={handleInstrumentChange}
              aria-label="Instruments"
              color="primary"
              fullWidth
            >
              <ToggleButton value="stocks">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Stocks</Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="etfs">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">ETFs</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Coming soon
                  </Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="funds" disabled>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Funds</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Coming soon
                  </Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="options" disabled>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Options</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Coming soon
                  </Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="futures" disabled>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Futures</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    Coming soon
                  </Typography>
                </Box>
              </ToggleButton>
            </ToggleButtonGroup>
            {errors.instruments && (
              <Typography color="error" variant="caption">{errors.instruments}</Typography>
            )}
          </Grid>
        </Grid>
      ),
      validate: () => !errors.name && !errors.regions && !errors.markets && !errors.instruments
    },
    
    {
      label: 'Investment Strategy',
      content: (
        <Grid container spacing={3}>
          <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
            <Typography variant="h6" gutterBottom>
              Investment Approach
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              The fundamental methodology used to make investment decisions
            </Typography>
            
            <ToggleButtonGroup
              value={formData.investmentApproaches}
              onChange={handleInvestmentApproachChange}
              aria-label="Investment Approach"
              color="primary"
              fullWidth
            >
              <ToggleButton value="quantitative">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Quantitative</Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="discretionary">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Discretionary</Typography>
                </Box>
              </ToggleButton>
            </ToggleButtonGroup>
            {errors.investmentApproaches && (
              <Typography color="error" variant="caption">{errors.investmentApproaches}</Typography>
            )}
          </Grid>
          
          <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
            <Typography variant="h6" gutterBottom>
              Investment Timeframe
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              The typical holding period for positions in the portfolio
            </Typography>
            
            <ToggleButtonGroup
              value={formData.investmentTimeframes}
              onChange={handleTimeframeChange}
              aria-label="Investment Timeframe"
              color="primary"
              fullWidth
            >
              <ToggleButton value="short">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Short-term</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    hours to days
                  </Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="medium">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Medium-term</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    days to weeks
                  </Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="long">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Long-term</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    weeks to months
                  </Typography>
                </Box>
              </ToggleButton>
            </ToggleButtonGroup>
            {errors.investmentTimeframes && (
              <Typography color="error" variant="caption">{errors.investmentTimeframes}</Typography>
            )}
          </Grid>
        </Grid>
      ),
      validate: () => !errors.investmentApproaches && !errors.investmentTimeframes
    },
    
    {
      label: 'Investment Focus',
      content: (
        <Grid container spacing={3}>
          <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
            <Typography variant="h6" gutterBottom>
              Investment Focus
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Sectors the portfolio specializes in
            </Typography>
            
            <Box sx={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 1
            }}>
              {/* Generalist button - full width */}
              <Box sx={{ gridColumn: '1 / span 3', mb: 1 }}>
                <ToggleButton
                  value="generalist"
                  selected={formData.sectors.includes('generalist')}
                  onClick={() => {
                    const newSelections = [...formData.sectors];
                    const hasGeneralist = newSelections.includes('generalist');
                    
                    if (hasGeneralist) {
                      const filteredSelections = newSelections.filter(id => id !== 'generalist');
                      handleSectorSelectionChange(filteredSelections);
                    } else {
                      handleSectorSelectionChange(['generalist', ...actualSectorIds]);
                    }
                  }}
                  color="primary"
                  fullWidth
                  sx={{
                    height: '56px'
                  }}
                >
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="body2">Generalist</Typography>
                    <Typography variant="caption" color="text.secondary" display="block">
                      All sectors
                    </Typography>
                  </Box>
                </ToggleButton>
              </Box>
              
              {/* Individual sector buttons - 3 columns */}
              {sectors.filter(s => s.value !== 'generalist').map((option) => (
                <ToggleButton 
                  key={option.value} 
                  value={option.value}
                  selected={formData.sectors.includes(option.value)}
                  onClick={() => {
                    const newSelections = [...formData.sectors];
                    const isSelected = newSelections.includes(option.value);
                    
                    if (isSelected) {
                      const filteredSelections = newSelections.filter(id => id !== option.value);
                      handleSectorSelectionChange(filteredSelections);
                    } else {
                      handleSectorSelectionChange([...newSelections, option.value]);
                    }
                  }}
                  color="primary"
                  sx={{ height: '48px' }}
                >
                  <Typography variant="body2">{option.label}</Typography>
                </ToggleButton>
              ))}
            </Box>
            {errors.sectors && (
              <Typography color="error" variant="caption">{errors.sectors}</Typography>
            )}
          </Grid>
        </Grid>
      ),
      validate: () => !errors.sectors
    },
    
    {
      label: 'Position & Capital',
      content: (
        <Grid container spacing={3}>
          <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
            <Typography variant="h6" gutterBottom>
              Position Types
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              The directional exposure strategy employed in the portfolio
            </Typography>
            
            <ToggleButtonGroup
              value={[
                ...(formData.positionTypes.long ? ['long'] : []),
                ...(formData.positionTypes.short ? ['short'] : [])
              ]}
              onChange={handlePositionTypeChange}
              aria-label="Position Types"
              color="primary"
              fullWidth
            >
              <ToggleButton value="long">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Long</Typography>
                </Box>
              </ToggleButton>
              <ToggleButton value="short">
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="body2">Short</Typography>
                </Box>
              </ToggleButton>
            </ToggleButtonGroup>
            {errors.positionTypes && (
              <Typography color="error" variant="caption">{errors.positionTypes}</Typography>
            )}
          </Grid>
          
          <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
            <Typography variant="h6" gutterBottom>
              Allocation
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Specify the managed allocation (in millions USD).
            </Typography>
            
            <FormHelperText>
              Base allocation: ${Math.round(formData.initialCapital / 1000000)}M | Recommended: ${Math.round(formData.initialCapital / 1000000)}M
            </FormHelperText>

            <FormControl fullWidth sx={{ mb: 3 }}>
              <StyledSlider
                value={formData.initialCapital / 1000000}
                onChange={(_, value) => {
                  updateField('initialCapital', (value as number) * 1000000);
                }}
                aria-labelledby="aum-slider"
                valueLabelDisplay="auto"
                valueLabelFormat={(value) => `$${value}M`}
                min={50}
                max={1000}
                step={50}
                marks={[
                  { value: 50, label: '$50M' },
                  { value: 100, label: '$100M' },
                  { value: 500, label: '$500M' },
                  { value: 1000, label: '$1000M' }
                ]}
              />
            </FormControl>
            {errors.initialCapital && (
              <Typography color="error" variant="caption">{errors.initialCapital}</Typography>
            )}
          </Grid>
        </Grid>
      ),
      validate: () => !errors.positionTypes && !errors.initialCapital
    },
    
    {
      label: 'Conviction Model',
      content: (
        <Grid container spacing={3}>
          <Grid {...{component: "div", item: true, xs: 12, size: 12} as any}>
            <ConvictionModelForm
              value={formData.convictionSchema}
              onChange={(value) => updateField('convictionSchema', value)}
            />
          </Grid>
        </Grid>
      ),
      validate: () => true
    }
  ];

  const handleSubmit = async (data: any) => {
    if (!validateForm()) {
      return { success: false, error: 'Please correct the validation errors' };
    }

    const bookData: BookRequest = {
      name: formData.name,
      regions: formData.regions,
      markets: formData.markets,
      instruments: formData.instruments,
      investmentApproaches: formData.investmentApproaches,
      investmentTimeframes: formData.investmentTimeframes,
      sectors: formData.sectors.filter(sector => sector !== 'generalist'),
      positionTypes: formData.positionTypes,
      initialCapital: formData.initialCapital,
      convictionSchema: formData.convictionSchema
    };

    return await onSubmit(bookData);
  };

  return (
    <FormContainer
      title={title}
      subtitle={subtitle}
      onBack={() => window.history.back()}
    >
      <FormWizard
        steps={steps}
        onSubmit={handleSubmit}
        submitButtonText={submitButtonText}
        title=""
        subtitle=""
      />
    </FormContainer>
  );
};

export default BaseBookForm;