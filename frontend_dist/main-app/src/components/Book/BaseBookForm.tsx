// src/components/Book/BaseBookForm.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Box, 
  Typography, 
  TextField, 
  FormControl,
  FormHelperText,
  ToggleButton,
  ToggleButtonGroup,
  Slider,
  Grid,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormGroup,
  Checkbox
} from '@mui/material';
import { styled } from '@mui/material/styles';
import { useToast } from '../../hooks/useToast';
import { BookRequest } from '@trading-app/types-core';
import { getLogger } from '@trading-app/logging'
import ConvictionModelForm from './ConvictionModelForm';
import { ConvictionModelConfig } from '@trading-app/types-core';
import { FormContainer, FormStepper, FormToggleGroup } from '../Form';
import './BaseBookForm.css';

const logger = getLogger('BaseBookForm');

const sectors = [
  { value: 'generalist', label: 'Generalist', description: 'All sectors' },
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

interface ExtendedBookRequest extends BookRequest {
  bookId?: string;
}

interface BaseBookFormProps {
  isEditMode: boolean;
  initialData?: Partial<ExtendedBookRequest>;
  onSubmit: (formData: BookRequest) => Promise<{ success: boolean; bookId?: string; error?: string }>;
  submitButtonText: string;
  title: string;
  subtitle: string;
}

const BaseBookForm: React.FC<BaseBookFormProps> = ({
  isEditMode,
  initialData = {},
  onSubmit,
  submitButtonText,
  title,
  subtitle
}) => {
  const navigate = useNavigate();
  const { addToast } = useToast();
  
  const [activeStep, setActiveStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [aumAllocation, setAumAllocation] = useState<number>(initialData.initialCapital ? initialData.initialCapital / 1000000 : 100);
  const [baseAumAllocation, setBaseAumAllocation] = useState<number>(initialData.initialCapital ? initialData.initialCapital / 1000000 : 100);

  // Form state
  const [bookName, setBookName] = useState(initialData.name || 'My Trading Book');
  const [regions, setRegions] = useState<string[]>(initialData.regions || ['us']);
  const [markets, setMarkets] = useState<string[]>(initialData.markets || ['equities']);
  const [instruments, setInstruments] = useState<string[]>(initialData.instruments || ['stocks']);
  const [investmentApproaches, setInvestmentApproaches] = useState<string[]>(initialData.investmentApproaches || []);
  const [timeframes, setTimeframes] = useState<string[]>(initialData.investmentTimeframes || []);
  const [selectedSectors, setSelectedSectors] = useState<string[]>(initialData.sectors || []);
  const [positionTypes, setPositionTypes] = useState<string[]>([
    ...(initialData.positionTypes?.long ? ['long'] : []), 
    ...(initialData.positionTypes?.short ? ['short'] : [])
  ]);
  const [initialCapital, setInitialCapital] = useState<number>(initialData.initialCapital || 100000000);

  const [convictionSchema, setConvictionSchema] = useState<ConvictionModelConfig>(
    initialData.convictionSchema || {
      portfolioApproach: 'incremental',
      targetConvictionMethod: 'percent',
      incrementalConvictionMethod: 'side_score',
      maxScore: 3,
      horizons: ['30m', '1h', '1d'],
    }
  );

  const steps = ['Basic Information', 'Investment Strategy', 'Investment Focus', 'Position & Capital', 'Conviction Model'];

  const handleNext = () => {
    const isValid = validateCurrentStep();
    if (isValid) {
      setActiveStep((prevStep) => prevStep + 1);
    }
  };
  
  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };
  
  const handleGoBack = () => {
    navigate('/home');
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    if (name) {
      if (name === 'name') {
        setBookName(value);
      } else if (name === 'initialCapital') {
        setInitialCapital(Number(value));
      }
      
      if (errors[name]) {
        setErrors(prev => {
          const newErrors = { ...prev };
          delete newErrors[name];
          return newErrors;
        });
      }
    }
  };
  
  const handleSectorSelectionChange = (newValue: string[]) => {
    if (isProcessing) return;
    
    setIsProcessing(true);
    
    try {
      const hasGeneralistBefore = selectedSectors.includes('generalist');
      const hasGeneralistAfter = newValue.includes('generalist');
      
      if (hasGeneralistBefore !== hasGeneralistAfter) {
        if (hasGeneralistAfter) {
          setSelectedSectors(['generalist', ...actualSectorIds]);
        } else {
          setSelectedSectors(selectedSectors.filter(id => id !== 'generalist'));
        }
        return;
      }
      
      if (hasGeneralistBefore && 
          hasGeneralistAfter && 
          newValue.length < selectedSectors.length) {
        const sectorBeingRemoved = selectedSectors.find(id => !newValue.includes(id) && id !== 'generalist');
        if (sectorBeingRemoved) {
          setSelectedSectors(selectedSectors.filter(id => id !== 'generalist' && id !== sectorBeingRemoved));
        }
        return;
      }
      
      const allSectorsSelected = actualSectorIds.every(sector => 
        newValue.includes(sector)
      );
      
      if (allSectorsSelected && !hasGeneralistAfter) {
        setSelectedSectors([...newValue, 'generalist']);
      } else {
        setSelectedSectors(newValue);
      }
      
      if (errors.sectors) {
        setErrors(prev => {
          const newErrors = { ...prev };
          delete newErrors.sectors;
          return newErrors;
        });
      }
    } finally {
      setTimeout(() => setIsProcessing(false), 0);
    }
  };
  
  const validateCurrentStep = () => {
    const newErrors: Record<string, string> = {};
    
    switch (activeStep) {
      case 0:
        if (!bookName.trim()) {
          newErrors.name = 'Book name is required';
        }
        if (regions.length === 0) {
          newErrors.regions = 'At least one region must be selected';
        }
        if (markets.length === 0) {
          newErrors.markets = 'At least one market must be selected';
        }
        if (instruments.length === 0) {
          newErrors.instruments = 'At least one instrument must be selected';
        }
        break;
        
      case 1:
        if (investmentApproaches.length === 0) {
          newErrors.investmentApproaches = 'Please select at least one investment approach';
        }
        if (timeframes.length === 0) {
          newErrors.investmentTimeframes = 'Please select at least one investment timeframe';
        }
        break;
        
      case 2:
        if (selectedSectors.length === 0) {
          newErrors.sectors = 'Please select at least one sector';
        }
        break;
        
      case 3:
        if (positionTypes.length === 0) {
          newErrors.positionTypes = 'Please select at least one position type';
        }
        if (!initialCapital || initialCapital <= 0) {
          newErrors.initialCapital = 'Please enter a valid initial capital amount';
        }
        break;
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateCurrentStep()) {
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const bookData: BookRequest = {
        name: bookName,
        regions: regions,
        markets: markets,
        instruments: instruments,
        investmentApproaches: investmentApproaches,
        investmentTimeframes: timeframes,
        sectors: selectedSectors.filter(sector => sector !== 'generalist'),
        positionTypes: {
          long: positionTypes.includes('long'),
          short: positionTypes.includes('short')
        },
        initialCapital: initialCapital,
        convictionSchema: convictionSchema 
      };
      
      const result = await onSubmit(bookData);
      
      if (result.success) {
        addToast('success', isEditMode ? 'Book updated successfully!' : 'Trading book created successfully!');
        
        if (isEditMode && initialData && 'bookId' in initialData) {
          navigate(`/books/${initialData.bookId}`);
        } else {
          navigate('/home');
        }
      } else {
        addToast('error', result.error || `Failed to ${isEditMode ? 'update' : 'create'} trading book`);
      }
    } catch (error: any) {
      addToast('error', `Error ${isEditMode ? 'updating' : 'creating'} trading book: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderBasicInformation = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <TextField
          fullWidth
          label="Book Name"
          name="name"
          value={bookName}
          onChange={handleInputChange}
          error={!!errors.name}
          helperText={errors.name}
          required
        />
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <FormToggleGroup
          title="Region"
          description="Geographic focus of the investment strategy"
          options={[
            { value: 'us', label: 'US Region' },
            { value: 'eu', label: 'EU Region', description: 'Coming soon' },
            { value: 'asia', label: 'Asia Region', description: 'Coming soon' },
            { value: 'emerging', label: 'Emerging', description: 'Coming soon' }
          ]}
          value={regions}
          onChange={setRegions}
          error={errors.regions}
        />
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <FormToggleGroup
          title="Markets"
          description="The markets accessed by the investment strategy"
          options={[
            { value: 'equities', label: 'Equities' },
            { value: 'bonds', label: 'Bonds', description: 'Coming soon' },
            { value: 'currencies', label: 'Currencies', description: 'Coming soon', disabled: true },
            { value: 'commodities', label: 'Commodities', description: 'Coming soon', disabled: true },
            { value: 'cryptos', label: 'Cryptos', description: 'Coming soon', disabled: true }
          ]}
          value={markets}
          onChange={setMarkets}
          error={errors.markets}
        />
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <FormToggleGroup
          title="Instruments"
          description="Financial instruments used in the portfolio"
          options={[
            { value: 'stocks', label: 'Stocks' },
            { value: 'etfs', label: 'ETFs', description: 'Coming soon' },
            { value: 'funds', label: 'Funds', description: 'Coming soon', disabled: true },
            { value: 'options', label: 'Options', description: 'Coming soon', disabled: true },
            { value: 'futures', label: 'Futures', description: 'Coming soon', disabled: true }
          ]}
          value={instruments}
          onChange={setInstruments}
          error={errors.instruments}
        />
      </Grid>
    </Grid>
  );
  
  const renderInvestmentStrategy = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <FormToggleGroup
          title="Investment Approach"
          description="The fundamental methodology used to make investment decisions"
          options={[
            { value: 'quantitative', label: 'Quantitative' },
            { value: 'discretionary', label: 'Discretionary' }
          ]}
          value={investmentApproaches}
          onChange={setInvestmentApproaches}
          error={errors.investmentApproaches}
          required
        />
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <FormToggleGroup
          title="Investment Timeframe"
          description="The typical holding period for positions in the portfolio"
          options={[
            { value: 'short', label: 'Short-term', description: 'hours to days' },
            { value: 'medium', label: 'Medium-term', description: 'days to weeks' },
            { value: 'long', label: 'Long-term', description: 'weeks to months' }
          ]}
          value={timeframes}
          onChange={setTimeframes}
          error={errors.investmentTimeframes}
          required
        />
      </Grid>
    </Grid>
  );
  
  const renderSectors = () => (
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
          <Box sx={{ gridColumn: '1 / span 3', mb: 1 }}>
            <ToggleButton
              value="generalist"
              selected={selectedSectors.includes('generalist')}
              onClick={() => {
                const newSelections = [...selectedSectors];
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
              sx={{ height: '56px' }}
            >
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="body2">Generalist</Typography>
                <Typography variant="caption" color="text.secondary" display="block">
                  All sectors
                </Typography>
              </Box>
            </ToggleButton>
          </Box>
          
          {sectors.filter(s => s.value !== 'generalist').map((option) => (
            <ToggleButton 
              key={option.value} 
              value={option.value}
              selected={selectedSectors.includes(option.value)}
              onClick={() => {
                const newSelections = [...selectedSectors];
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
  );
  
  const renderPositionAndCapital = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <FormToggleGroup
          title="Position Types"
          description="The directional exposure strategy employed in the portfolio"
          options={[
            { value: 'long', label: 'Long' },
            { value: 'short', label: 'Short' }
          ]}
          value={positionTypes}
          onChange={setPositionTypes}
          error={errors.positionTypes}
          required
        />
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <Typography variant="h6" gutterBottom>
          Allocation
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Specify the managed allocation (in millions USD).
        </Typography>
        
        <FormHelperText>
          Base allocation: ${baseAumAllocation}M | Recommended: ${aumAllocation}M
        </FormHelperText>

        <FormControl fullWidth sx={{ mb: 3 }}>
          <StyledSlider
            value={baseAumAllocation}
            onChange={(_, value) => {
              setBaseAumAllocation(value as number);
              setInitialCapital((value as number) * 1000000);
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
  );
  
  const renderConvictionModelSection = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12, size: 12} as any}>
        <ConvictionModelForm
          value={convictionSchema}
          onChange={(newSchema) => {
            console.log('BaseBookForm onChange called with:', newSchema); // Debug log
            setConvictionSchema(newSchema);
          }}
        />
      </Grid>
    </Grid>
  );

  const renderStepContent = (step: number) => {
    switch (step) {
      case 0:
        return renderBasicInformation();
      case 1:
        return renderInvestmentStrategy();
      case 2:
        return renderSectors();
      case 3:
        return renderPositionAndCapital();
      case 4:
        return renderConvictionModelSection();
      default:
        return null;
    }
  };

  return (
    <FormContainer 
      title={title} 
      subtitle={subtitle} 
      onBack={handleGoBack}
    >
      <FormStepper
        activeStep={activeStep}
        steps={steps}
        onNext={handleNext}
        onBack={handleBack}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
        submitButtonText={submitButtonText}
      >
        {renderStepContent(activeStep)}
      </FormStepper>
    </FormContainer>
  );
};

export default BaseBookForm;