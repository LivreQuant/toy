// src/components/Book/BaseBookForm.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Box, 
  Button, 
  Typography, 
  TextField, 
  Paper, 
  Stepper, 
  Step, 
  StepLabel,
  Divider,
  FormControl,
  FormHelperText,
  ToggleButton,
  ToggleButtonGroup,
  Slider,
  Grid,
  CircularProgress,
  Chip,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormGroup,
  Checkbox
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { styled } from '@mui/material/styles';
import { useToast } from '../../hooks/useToast';
import { BookRequest } from '@shared/types';
import { getLogger } from '../../boot/logging';
import ConvictionModelForm from './ConvictionModelForm';
import { ConvictionModelConfig } from '@shared/types';
import './BaseBookForm.css';

// Initialize logger
const logger = getLogger('BaseBookForm');

// Reuse the same sectors, market values, etc. from your current forms
const sectors = [
  { id: 'generalist', label: 'Generalist', examples: 'All sectors' },
  { id: 'tech', label: 'Technology' },
  { id: 'healthcare', label: 'Healthcare' },
  { id: 'financials', label: 'Financials' },
  { id: 'consumer', label: 'Consumer' },
  { id: 'industrials', label: 'Industrials' },
  { id: 'energy', label: 'Energy' },
  { id: 'materials', label: 'Materials' },
  { id: 'utilities', label: 'Utilities' },
  { id: 'realestate', label: 'Real Estate' }
];

const actualSectorIds = sectors
  .filter(sector => sector.id !== 'generalist')
  .map(sector => sector.id);

// StyledSlider component from BookSetupPage
const StyledSlider = styled(Slider)(({ theme }) => ({
  // Target the first mark label (50M)
  '& .MuiSlider-markLabel[data-index="0"]': {
    transform: 'translateX(0%)',
    left: '0%',
  },
  // Target the second mark label (100M)
  '& .MuiSlider-markLabel[data-index="1"]': {
    transform: 'translateX(0%)',
    left: '50%',
  },
  // Target the third mark label (500M)
  '& .MuiSlider-markLabel[data-index="2"]': {
    transform: 'translateX(-50%)',
    left: '100%',
  },
  // Target the fourth mark label (1000M)
  '& .MuiSlider-markLabel[data-index="3"]': {
    transform: 'translateX(-100%)',
    left: '100%',
  },
}));


// Extended interface to include bookId for edit mode
interface ExtendedBookRequest extends BookRequest {
  bookId?: string;
}

interface BaseBookFormProps {
  isEditMode: boolean;
  initialData?: Partial<ExtendedBookRequest>; // <-- Change this line
  onSubmit: (formData: BookRequest) => Promise<{ success: boolean; bookId?: string; error?: string }>;
  submitButtonText: string;
  title: string;
  subtitle: string;
}

const BaseBookForm: React.FC<BaseBookFormProps> = ({
  isEditMode,
  initialData = {}, // Empty object as default
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

  // Custom state for handling AUM allocation
  const [aumAllocation, setAumAllocation] = useState<number>(initialData.initialCapital ? initialData.initialCapital / 1000000 : 100);
  const [baseAumAllocation, setBaseAumAllocation] = useState<number>(initialData.initialCapital ? initialData.initialCapital / 1000000 : 100);

  // Initialize form state with initialData or defaults
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

  // Steps array (same for both forms)
  const steps = ['Basic Information', 'Investment Strategy', 'Investment Focus', 'Position & Capital', 'Conviction Model'];

  // All the validation, event handlers, and form logic
  // ... (include all the necessary handlers from your existing form)
  
  const handleNext = () => {
    // Validate current step
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

  // Handle text input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    if (name) {
      if (name === 'name') {
        setBookName(value);
      } else if (name === 'initialCapital') {
        setInitialCapital(Number(value));
      }
      
      // Clear error when field is updated
      if (errors[name]) {
        setErrors(prev => {
          const newErrors = { ...prev };
          delete newErrors[name];
          return newErrors;
        });
      }
    }
  };
  
  // Handle toggle button selection changes
  const handleToggleChange = (categoryId: string, newValue: string | string[]) => {
    if (categoryId === 'sectors') {
      handleSectorSelectionChange(newValue as string[]);
    } else {
      logger.debug(`Selection changed for ${categoryId}`, { 
        previous: categoryId === 'regions' ? regions : 
                 categoryId === 'markets' ? markets :
                 categoryId === 'instruments' ? instruments :
                 categoryId === 'investmentApproaches' ? investmentApproaches :
                 categoryId === 'investmentTimeframes' ? timeframes :
                 categoryId === 'positionTypes' ? positionTypes : [],
        new: newValue 
      });
      
      // Set the state based on the category
      switch(categoryId) {
        case 'regions':
          setRegions(newValue as string[] || []);
          break;
        case 'markets':
          setMarkets(newValue as string[] || []);
          break;
        case 'instruments':
          setInstruments(newValue as string[] || []);
          break;
        case 'investmentApproaches':
          setInvestmentApproaches(newValue as string[] || []);
          break;
        case 'investmentTimeframes':
          setTimeframes(newValue as string[] || []);
          break;
        case 'positionTypes':
          setPositionTypes(newValue as string[] || []);
          break;
      }
      
      // Clear error when field is updated
      if (errors[categoryId]) {
        setErrors(prev => {
          const newErrors = { ...prev };
          delete newErrors[categoryId];
          return newErrors;
        });
      }
    }
  };

  // REFACTORED: Handle selection changes for the sector focus category
  const handleSectorSelectionChange = (newValue: string[]) => {
    if (isProcessing) return;
    
    setIsProcessing(true);
    
    try {
      // Force specific behaviors based on what changed
      const hasGeneralistBefore = selectedSectors.includes('generalist');
      const hasGeneralistAfter = newValue.includes('generalist');
      
      // Case 1: Generalist was toggled directly
      if (hasGeneralistBefore !== hasGeneralistAfter) {
        if (hasGeneralistAfter) {
          // Generalist turned ON - select all sectors
          setSelectedSectors(['generalist', ...actualSectorIds]);
        } else {
          // Generalist turned OFF - remove generalist but keep other sectors
          setSelectedSectors(selectedSectors.filter(id => id !== 'generalist'));
        }
        return;
      }
      
      // Case 2: An individual sector was toggled while generalist is selected
      if (hasGeneralistBefore && 
          hasGeneralistAfter && 
          newValue.length < selectedSectors.length) {
        // A sector was deselected while generalist was on - remove generalist too
        const sectorBeingRemoved = selectedSectors.find(id => !newValue.includes(id) && id !== 'generalist');
        if (sectorBeingRemoved) {
          setSelectedSectors(selectedSectors.filter(id => id !== 'generalist' && id !== sectorBeingRemoved));
        }
        return;
      }
      
      // Case 3: Normal selection update (adding sectors)
      const allSectorsSelected = actualSectorIds.every(sector => 
        newValue.includes(sector)
      );
      
      if (allSectorsSelected && !hasGeneralistAfter) {
        // All sectors are selected - add generalist too
        setSelectedSectors([...newValue, 'generalist']);
      } else {
        // Normal update
        setSelectedSectors(newValue);
      }
      
      // Clear error when field is updated
      if (errors.sectors) {
        setErrors(prev => {
          const newErrors = { ...prev };
          delete newErrors.sectors;
          return newErrors;
        });
      }
    } finally {
      // Use setTimeout to break the update cycle
      setTimeout(() => setIsProcessing(false), 0);
    }
  };
  
  // Include all your form validation logic here
  const validateCurrentStep = () => {
    const newErrors: Record<string, string> = {};
    
    switch (activeStep) {
      case 0: // Basic Information
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
        
      case 1: // Investment Strategy
        if (investmentApproaches.length === 0) {
          newErrors.investmentApproaches = 'Please select at least one investment approach';
        }
        if (timeframes.length === 0) {
          newErrors.investmentTimeframes = 'Please select at least one investment timeframe';
        }
        break;
        
      case 2: // Sector Focus
        if (selectedSectors.length === 0) {
          newErrors.sectors = 'Please select at least one sector';
        }
        break;
        
      case 3: // Position & Capital
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

  // Include sector selection handling and all other handlers

  // Create the submit handler
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Final validation
    if (!validateCurrentStep()) {
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      // Prepare the book data in the format expected by the API
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
        
        // Handle navigation based on mode
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
        <Typography variant="h6" gutterBottom>
          Region
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Geographic focus of the investment strategy
        </Typography>
        
        <ToggleButtonGroup
          value={regions}
          onChange={(_, value) => handleToggleChange('regions', value)}
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
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <Typography variant="h6" gutterBottom>
          Markets
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          The markets accessed by the investment strategy
        </Typography>
        
        
        <ToggleButtonGroup
          value={markets}
          onChange={(_, value) => handleToggleChange('markets', value)}
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
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <Typography variant="h6" gutterBottom>
          Instruments
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Financial instruments used in the portfolio
        </Typography>
        
        <ToggleButtonGroup
          value={instruments}
          onChange={(_, value) => handleToggleChange('instruments', value)}
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
      </Grid>
    </Grid>
  );
  
  const renderInvestmentStrategy = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <Typography variant="h6" gutterBottom>
          Investment Approach
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          The fundamental methodology used to make investment decisions
        </Typography>
        
        <ToggleButtonGroup
          value={investmentApproaches}
          onChange={(_, value) => handleToggleChange('investmentApproaches', value)}
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
          value={timeframes}
          onChange={(_, value) => handleToggleChange('investmentTimeframes', value)}
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
          {/* Generalist button - full width */}
          <Box sx={{ gridColumn: '1 / span 3', mb: 1 }}>
            <ToggleButton
              value="generalist"
              selected={selectedSectors.includes('generalist')}
              onClick={() => {
                // Directly toggle generalist without using ToggleButtonGroup
                const newSelections = [...selectedSectors];
                const hasGeneralist = newSelections.includes('generalist');
                
                if (hasGeneralist) {
                  // Remove generalist
                  const filteredSelections = newSelections.filter(id => id !== 'generalist');
                  handleSectorSelectionChange(filteredSelections);
                } else {
                  // Add generalist and all sectors
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
          {sectors.filter(s => s.id !== 'generalist').map((option) => (
            <ToggleButton 
              key={option.id} 
              value={option.id}
              selected={selectedSectors.includes(option.id)}
              onClick={() => {
                // Directly toggle this specific sector
                const newSelections = [...selectedSectors];
                const isSelected = newSelections.includes(option.id);
                
                if (isSelected) {
                  // Remove this sector
                  const filteredSelections = newSelections.filter(id => id !== option.id);
                  handleSectorSelectionChange(filteredSelections);
                } else {
                  // Add this sector
                  handleSectorSelectionChange([...newSelections, option.id]);
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
        <Typography variant="h6" gutterBottom>
          Position Types
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          The directional exposure strategy employed in the portfolio
        </Typography>
        
        <ToggleButtonGroup
          value={positionTypes}
          onChange={(_, value) => handleToggleChange('positionTypes', value)}
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
  
  // Add this function to BaseBookForm.tsx component
  const renderConvictionModelSection = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12, size: 12} as any}>
        <ConvictionModelForm
          value={convictionSchema}
          onChange={setConvictionSchema}
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
    <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
      <Button 
        startIcon={<ArrowBackIcon />} 
        onClick={handleGoBack}
        variant="outlined"
        sx={{ mr: 2, mb: 4 }}
      >
        Back to Home
      </Button>
      
      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          {title}
        </Typography>
        
        <Typography variant="subtitle1" color="text.secondary" paragraph align="center">
          {subtitle}
        </Typography>
        
        <Stepper activeStep={activeStep} sx={{ mb: 4, pt: 2, pb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
        
        <Divider sx={{ mb: 4 }} />
        
        <form onSubmit={(e) => { e.preventDefault(); handleNext(); }}>
          {renderStepContent(activeStep)}
          
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4, pt: 2 }}>
            <Button
              disabled={activeStep === 0}
              onClick={handleBack}
              variant="outlined"
            >
              Back
            </Button>
            
            {activeStep < steps.length - 1 ? (
              <Button 
                variant="contained" 
                color="primary" 
                onClick={handleNext}
              >
                Next
              </Button>
            ) : (
              <Button 
                variant="contained" 
                color="primary" 
                onClick={handleSubmit}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <CircularProgress size={24} sx={{ mr: 1 }} />
                    {submitButtonText}...
                  </>
                ) : (
                  submitButtonText
                )}
              </Button>
            )}
          </Box>
        </form>
      </Paper>
    </Box>
  );
};

export default BaseBookForm;