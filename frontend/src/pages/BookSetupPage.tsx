// src/pages/BookSetupPage.tsx
import React, { useState, useEffect } from 'react';
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
  CircularProgress
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { styled } from '@mui/material/styles';
import { useToast } from '../hooks/useToast';
import { useBookManager } from '../hooks/useBookManager';
import { useConnection } from '../hooks/useConnection';
import { getLogger } from '../boot/logging';
import { BookRequest } from '../types';
import './BookSetupPage.css';

// Initialize logger
const logger = getLogger('BookSetupPage');

// Define the book setup data structure
interface BookSetupData {
  // Basic Information
  name: string;

  regions: string[];
  markets: string[];
  instruments: string[];
  
  // Investment Strategy
  investmentApproaches: string[];
  investmentTimeframes: string[];
  
  // Sector Focus
  sectors: string[];
  
  // Position Types and Capital
  positionTypes: string[];
  initialCapital: number;
}

// Define the option types
interface CategoryOption {
  id: string;
  label: string;
  examples?: string;
}

// Define the market keys to ensure type safety
type MarketKey = 'equities' | 'bonds' | 'currencies' | 'commodities' | 'cryptos';

// Create the market AUM values with proper typing
const marketAumValues: Record<MarketKey, number> = {
  equities: 100,   // $100M for equities
  bonds: 200,      // $200M for bonds
  currencies: 150, // $150M for currencies
  commodities: 300, // $300M for commodities
  cryptos: 80      // $80M for cryptos
};

// AUM allocation modifiers by category
const aumModifiers = {
  region: {
    us: 1.0,     // Base modifier
    eu: 0.8,     // 80% of US
    asia: 0.7,   // 70% of US
    emerging: 0.5 // 50% of US
  },
  markets: {
    equities: 1.0,
    bonds: 0.8,
    currencies: 0.6,
    commodities: 0.7,
    crypto: 0.7
  },
  investmentApproaches: {
    quantitative: 1.2,  // Quant strategies often manage more capital
    discretionary: 0.9
  },
  investmentTimeframes: {
    short: 0.8,  // Short-term strategies often have lower capacity
    medium: 1.0,
    long: 1.2    // Long-term strategies can often manage more capital
  }
};

// Define sectors
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

// Define the actual sector IDs (excluding generalist)
const actualSectorIds = sectors
  .filter(sector => sector.id !== 'generalist')
  .map(sector => sector.id);

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

const BookSetupPage: React.FC = () => {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const bookManager = useBookManager();
  const { isConnected } = useConnection();
  
  const [activeStep, setActiveStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  // Custom state for handling AUM allocation
  const [aumAllocation, setAumAllocation] = useState<number>(100); // Default value in millions
  const [baseAumAllocation, setBaseAumAllocation] = useState<number>(100); // User-selected base value
  
  // Default values
  const [formData, setFormData] = useState<BookSetupData>({
    name: 'My Trading Book',
    regions: ['us'],
    markets: ['equities'],
    instruments: ['stocks'],
    investmentApproaches: [],
    investmentTimeframes: [],
    sectors: [],
    positionTypes: [],
    initialCapital: 100000000 // 100M in dollars
  });
  
  const steps = ['Basic Information', 'Investment Strategy', 'Investment Focus', 'Position & Capital'];
  
  // Calculate recommended AUM based on selections
  useEffect(() => {
    let multiplier = 1.0;
    
    // Apply region modifier - use the first region in the array
    if (formData.regions.includes('us')) multiplier *= aumModifiers.region.us;
    else if (formData.regions.includes('eu')) multiplier *= aumModifiers.region.eu;
    else if (formData.regions.includes('asia')) multiplier *= aumModifiers.region.asia;
    else if (formData.regions.includes('emerging')) multiplier *= aumModifiers.region.emerging;
    
    // Apply markets modifier - use the first market in the array
    if (formData.markets.includes('equities')) multiplier *= aumModifiers.markets.equities;
    else if (formData.markets.includes('bonds')) multiplier *= aumModifiers.markets.bonds;
    else if (formData.markets.includes('currencies')) multiplier *= aumModifiers.markets.currencies;
    else if (formData.markets.includes('commodities')) multiplier *= aumModifiers.markets.commodities;
    else if (formData.markets.includes('cryptos')) multiplier *= aumModifiers.markets.crypto;
    
    // Apply investment approach modifier
    if (formData.investmentApproaches.includes('quantitative')) {
      multiplier *= aumModifiers.investmentApproaches.quantitative;
    } else if (formData.investmentApproaches.includes('discretionary')) {
      multiplier *= aumModifiers.investmentApproaches.discretionary;
    }
    
    // Apply timeframe modifier (use the longest timeframe selected)
    if (formData.investmentTimeframes.includes('long')) {
      multiplier *= aumModifiers.investmentTimeframes.long;
    } else if (formData.investmentTimeframes.includes('medium')) {
      multiplier *= aumModifiers.investmentTimeframes.medium;
    } else if (formData.investmentTimeframes.includes('short')) {
      multiplier *= aumModifiers.investmentTimeframes.short;
    }
      
    // If no market is selected, use a default value
    if (!formData.markets) {
      setAumAllocation(baseAumAllocation); // Use the base value
      return;
    }
    
    // Set AUM based on the selected market with type checking  
    const marketKey = formData.markets[0] as MarketKey;
    const marketValue = marketAumValues[marketKey] || 100;
    const calculatedValue = Math.round(marketValue * multiplier);
    
    // Update the AUM allocation and the form data
    setAumAllocation(calculatedValue);
    setFormData(prev => ({
      ...prev,
      initialCapital: calculatedValue * 1000000 // Convert to dollars (from millions)
    }));
    
  }, [formData.regions, formData.markets, formData.investmentApproaches, formData.investmentTimeframes, baseAumAllocation]);
  
  // REMOVED the problematic useEffect for sector handling
  
  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };
  
  const handleNext = () => {
    // Validate current step
    const isValid = validateCurrentStep();
    if (isValid) {
      setActiveStep((prevStep) => prevStep + 1);
    }
  };
  
  const validateCurrentStep = () => {
    const newErrors: Record<string, string> = {};
    
    switch (activeStep) {
      case 0: // Basic Information
        if (!formData.name.trim()) {
          newErrors.name = 'Book name is required';
        }
        if (formData.regions.length === 0) {
          newErrors.regions = 'At least one region must be selected';
        }
        if (formData.markets.length === 0) {
          newErrors.markets = 'At least one market must be selected';
        }
        if (formData.instruments.length === 0) {
          newErrors.instruments = 'At least one instrument must be selected';
        }
        break;
        
      case 1: // Investment Strategy
        if (formData.investmentApproaches.length === 0) {
          newErrors.investmentApproaches = 'Please select at least one investment approach';
        }
        if (formData.investmentTimeframes.length === 0) {
          newErrors.investmentTimeframes = 'Please select at least one investment timeframe';
        }
        break;
        
      case 2: // Sector Focus
        if (formData.sectors.length === 0) {
          newErrors.sectors = 'Please select at least one sector';
        }
        break;
        
      case 3: // Position & Capital
        if (formData.positionTypes.length === 0) {
          newErrors.positionTypes = 'Please select at least one position type';
        }
        if (!formData.initialCapital || formData.initialCapital <= 0) {
          newErrors.initialCapital = 'Please enter a valid initial capital amount';
        }
        break;
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleGoBack = () => {
    navigate('/home');
  };
  
  // Handle text input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    if (name) {
      setFormData(prev => ({
        ...prev,
        [name]: value
      }));
      
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
      logger.debug(`Selection changed for ${categoryId}`, { previous: formData[categoryId as keyof BookSetupData], new: newValue });
      
      // Make sure we're correctly setting the formData for each category
      switch(categoryId) {
        case 'regions':
          setFormData(prev => ({
            ...prev,
            regions: newValue as string[]
          }));
          break;
        case 'markets':
          setFormData(prev => ({
            ...prev,
            markets: newValue as string[]
          }));
          break;
        case 'instruments':
          setFormData(prev => ({
            ...prev,
            instruments: newValue as string[]
          }));
          break;
        case 'investmentApproaches':
          setFormData(prev => ({
            ...prev,
            investmentApproaches: newValue as string[]
          }));
          break;
        case 'investmentTimeframes':
          setFormData(prev => ({
            ...prev,
            investmentTimeframes: newValue as string[]
          }));
          break;
        case 'positionTypes':
          setFormData(prev => ({
            ...prev,
            positionTypes: newValue as string[]
          }));
          break;
        default:
          setFormData(prev => ({
            ...prev,
            [categoryId]: newValue
          }));
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
      const hasGeneralistBefore = formData.sectors.includes('generalist');
      const hasGeneralistAfter = newValue.includes('generalist');
      
      // Case 1: Generalist was toggled directly
      if (hasGeneralistBefore !== hasGeneralistAfter) {
        if (hasGeneralistAfter) {
          // Generalist turned ON - select all sectors
          setFormData(prev => ({
            ...prev,
            sectors: ['generalist', ...actualSectorIds]
          }));
        } else {
          // Generalist turned OFF - remove generalist but keep other sectors
          setFormData(prev => ({
            ...prev,
            sectors: prev.sectors.filter(id => id !== 'generalist')
          }));
        }
        return;
      }
      
      // Case 2: An individual sector was toggled while generalist is selected
      if (hasGeneralistBefore && 
          hasGeneralistAfter && 
          newValue.length < formData.sectors.length) {
        // A sector was deselected while generalist was on - remove generalist too
        const sectorBeingRemoved = formData.sectors.find(id => !newValue.includes(id) && id !== 'generalist');
        if (sectorBeingRemoved) {
          setFormData(prev => ({
            ...prev,
            sectors: prev.sectors.filter(id => id !== 'generalist' && id !== sectorBeingRemoved)
          }));
        }
        return;
      }
      
      // Case 3: Normal selection update (adding sectors)
      const allSectorsSelected = actualSectorIds.every(sector => 
        newValue.includes(sector)
      );
      
      if (allSectorsSelected && !hasGeneralistAfter) {
        // All sectors are selected - add generalist too
        setFormData(prev => ({
          ...prev,
          sectors: [...newValue, 'generalist']
        }));
      } else {
        // Normal update
        setFormData(prev => ({
          ...prev,
          sectors: newValue
        }));
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
  
  
  const handleSubmit = async () => {
    // Final validation
    if (!validateCurrentStep()) {
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      // Convert form data to new API format
      const bookData: BookRequest = {
        name: formData.name,
        regions: formData.regions,
        markets: formData.markets,
        instruments: formData.instruments,
        investmentApproaches: formData.investmentApproaches,
        investmentTimeframes: formData.investmentTimeframes,
        sectors: formData.sectors.filter(sector => sector !== 'generalist'),
        positionTypes: {
          long: formData.positionTypes.includes('long'),
          short: formData.positionTypes.includes('short')
        },
        initialCapital: formData.initialCapital
      };
      
      const result = await bookManager.createBook(bookData);
      
      if (result.success) {
        addToast('success', 'Trading book created successfully!');
        navigate('/home');
      } else {
        addToast('error', result.error || 'Failed to create trading book');
      }
    } catch (error: any) {
      addToast('error', `Error creating trading book: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Render step content
  const renderStepContent = () => {
    switch (activeStep) {
      case 0:
        return renderBasicInformation();
      case 1:
        return renderInvestmentStrategy();
      case 2:
        return renderSectors();
      case 3:
        return renderPositionAndCapital();
      default:
        return null;
    }
  };
  
  const renderBasicInformation = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12, sx: { width: "100%" }} as any}>
        <TextField
          fullWidth
          label="Book Name"
          name="name"
          value={formData.name}
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
          value={formData.regions}
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
          value={formData.markets}
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
          value={formData.instruments}
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
          value={formData.investmentApproaches}
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
          value={formData.investmentTimeframes}
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
              selected={formData.sectors.includes('generalist')}
              onClick={() => {
                // Directly toggle generalist without using ToggleButtonGroup
                const newSelections = [...formData.sectors];
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
              selected={formData.sectors.includes(option.id)}
              onClick={() => {
                // Directly toggle this specific sector
                const newSelections = [...formData.sectors];
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
          value={formData.positionTypes}
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
            onChange={(_, value) => setBaseAumAllocation(value as number)}
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
          Portfolio Preferences
        </Typography>
        
        <Typography variant="subtitle1" color="text.secondary" paragraph align="center">
          Configure your preferences step by step
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
         {renderStepContent()}
         
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
               disabled={isSubmitting || !isConnected}
             >
               {isSubmitting ? (
                 <>
                   <CircularProgress size={24} sx={{ mr: 1 }} />
                   Creating Portfolio...
                 </>
               ) : (
                 'Generate Simulation'
               )}
             </Button>
           )}
         </Box>
       </form>
     </Paper>
   </Box>
 );
};

export default BookSetupPage;