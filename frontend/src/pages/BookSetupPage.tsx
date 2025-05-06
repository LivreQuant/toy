// src/pages/BookSetupPage.tsx
import React, { useState, useEffect, useContext } from 'react';
import { getLogger } from '../boot/logging';
import { BookManagerContext } from '../contexts/BookContext';
import { 
  Box, 
  Button, 
  Typography, 
  Paper,
  ToggleButton, 
  ToggleButtonGroup,
  Slider,
  FormControl,
  FormHelperText
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { styled } from '@mui/material/styles';
import { TextField } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';


// Initialize logger
const logger = getLogger('BookSetupPage');

// Define the option types
interface CategoryOption {
  id: string;
  label: string;
  examples?: string;
}

interface CategoryConfig {
  id: string;
  title: string;
  description: string;
  options: CategoryOption[];
  multiSelect: boolean;
  disabled?: boolean;
  defaultValue?: string | string[];
}

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

// Define a type for the market keys to ensure type safety
type MarketKey = 'equities' | 'bonds' | 'currencies' | 'commodities' | 'cryptos';

// Create the market AUM values with proper typing
const marketAumValues: Record<MarketKey, number> = {
  equities: 100,   // $100M for equities
  bonds: 200,      // $200M for bonds
  currencies: 150, // $150M for currencies
  commodities: 300, // $300M for commodities
  cryptos: 80      // $80M for cryptos
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
  investmentApproach: {
    quantitative: 1.2,  // Quant strategies often manage more capital
    discretionary: 0.9
  },
  investmentTimeframe: {
    short: 0.8,  // Short-term strategies often have lower capacity
    medium: 1.0,
    long: 1.2    // Long-term strategies can often manage more capital
  }
};

const BookSetupPage: React.FC = () => {
  const navigate = useNavigate();
  
  // Add this function to handle navigation
  const handleBackToHome = () => {
    navigate('/home');
  };

  const [portfolioName, setPortfolioName] = useState<string>('My Portfolio');

  // Get the book manager from context
  const bookManagerContext = useContext(BookManagerContext);
  if (!bookManagerContext) {
    throw new Error('BookManager context is undefined');
  }
  const { createBook, fetchBooks, fetchBook } = bookManagerContext;

  // Define the categories and their options
  const categories: CategoryConfig[] = [
    {
      id: 'region',
      title: 'Regions',
      description: 'Geographic focus of the investment strategy',
      options: [
        { id: 'us', label: 'US Region' },
        { id: 'eu', label: 'EU Region', examples: 'Coming soon' },
        { id: 'asia', label: 'Asia Region', examples: 'Coming soon' },
        { id: 'emerging', label: 'Emerging', examples: 'Coming soon' }
      ],
      multiSelect: false,
      defaultValue: 'us',
      disabled: true
    },
    {
      id: 'markets',
      title: 'Markets',
      description: 'The markets accessed by the investment strategy',
      options: [
        { id: 'equities', label: 'Equities' },
        { id: 'bonds', label: 'Bonds', examples: 'Coming soon' },
        { id: 'currencies', label: 'Currencies', examples: 'Coming soon' },
        { id: 'commodities', label: 'Commodities', examples: 'Coming soon' },
        { id: 'cryptos', label: 'Cryptos', examples: 'Coming soon' }
      ],
      multiSelect: false,
      defaultValue: 'equities',
      disabled: true
    },
    {
      id: 'instruments',
      title: 'Instruments',
      description: 'Financial instruments used in the portfolio',
      options: [
        { id: 'stocks', label: 'Stocks' },
        { id: 'etfs', label: 'ETFs', examples: 'Coming soon' },
        { id: 'funds', label: 'Funds', examples: 'Coming soon' },
        { id: 'options', label: 'Options', examples: 'Coming soon' },
        { id: 'futures', label: 'Futures', examples: 'Coming soon' },
        { id: 'bonds', label: 'Bonds', examples: 'Coming soon' },
        { id: 'cryptos', label: 'Cryptos', examples: 'Coming soon' }
      ],
      multiSelect: false,
      defaultValue: 'stocks',
      disabled: true
    },
    {
      id: 'investmentApproach',
      title: 'Investment Approach',
      description: 'The fundamental methodology used to make investment decisions',
      options: [
        { id: 'quantitative', label: 'Quantitative', examples: '' },
        { id: 'discretionary', label: 'Discretionary', examples: '' },
      ],
      multiSelect: true
    },
    {
      id: 'investmentTimeframe',
      title: 'Investment Timeframe',
      description: 'The typical holding period for positions in the portfolio',
      options: [
        { id: 'short', label: 'Short-term', examples: 'hours to days' },
        { id: 'medium', label: 'Medium-term', examples: 'days to weeks' },
        { id: 'long', label: 'Long-term', examples: 'weeks to months' }
      ],
      multiSelect: true
    },
    {
      id: 'sectorFocus',
      title: 'Sector Focus',
      description: 'Sectors the portfolio specializes in',
      options: sectors,
      multiSelect: true
    },
    {
      id: 'positionTypes',
      title: 'Position Types',
      description: 'The directional exposure strategy employed in the portfolio',
      options: [
        { id: 'long', label: 'Long', examples: '' },
        { id: 'short', label: 'Short', examples: '' }
      ],
      multiSelect: true
    }
  ];

  // Function to convert selections to the required format for CreateBookRequest
  const convertSelectionsToParameters = (): Array<[string, string, string]> => {
    const parameters: Array<[string, string, string]> = [];
    
    // Add region
    if (selections.region.length > 0) {
      parameters.push(["Region", "", selections.region[0]]);
    }
    
    // Add markets
    if (selections.markets.length > 0) {
      parameters.push(["Market", "", selections.markets[0]]);
    }
    
    // Add instruments
    if (selections.instruments.length > 0) {
      parameters.push(["Instrument", "", selections.instruments[0]]);
    }
    
    // Add investment approach (can have multiple)
    selections.investmentApproach.forEach(approach => {
      parameters.push(["Investment Approach", "", approach]);
    });
    
    // Add investment timeframe (can have multiple)
    selections.investmentTimeframe.forEach(timeframe => {
      parameters.push(["Investment Timeframe", "", timeframe]);
    });
    
    // Add sector focus (can have multiple)
    selections.sectorFocus.forEach(sector => {
      parameters.push(["Sector", "", sector]);
    });
    
    // Add position types (long/short)
    const hasLong = selections.positionTypes.includes('long');
    const hasShort = selections.positionTypes.includes('short');
    parameters.push(["Position", "Long", hasLong.toString()]);
    parameters.push(["Position", "Short", hasShort.toString()]);
    
    // Add AUM allocation
    parameters.push(["Allocation", "", aumAllocation.toString()]);
    
    return parameters;
  };

  // State for selected options in each category
  const [selections, setSelections] = useState<Record<string, string[]>>(() => {
    // Initialize with default values where applicable
    const initialSelections: Record<string, string[]> = {};
    categories.forEach(category => {
      if (category.defaultValue) {
        initialSelections[category.id] = Array.isArray(category.defaultValue) 
          ? category.defaultValue 
          : [category.defaultValue];
      } else {
        initialSelections[category.id] = [];
      }
    });
    return initialSelections;
  });

  // Flag to prevent infinite loops
  const [isProcessing, setIsProcessing] = useState(false);

  // State for AUM allocation
  const [aumAllocation, setAumAllocation] = useState<number>(100); // Default value in millions
  const [baseAumAllocation, setBaseAumAllocation] = useState<number>(100); // User-selected base value

  // Calculate recommended AUM based on selections
  useEffect(() => {
    let multiplier = 1.0;
    
    // Apply region modifier
    if (selections.region.includes('us')) multiplier *= aumModifiers.region.us;
    else if (selections.region.includes('eu')) multiplier *= aumModifiers.region.eu;
    else if (selections.region.includes('asia')) multiplier *= aumModifiers.region.asia;
    else if (selections.region.includes('emerging')) multiplier *= aumModifiers.region.emerging;
    
    // Apply markets modifier
    if (selections.markets.includes('equities')) multiplier *= aumModifiers.markets.equities;
    else if (selections.markets.includes('bonds')) multiplier *= aumModifiers.markets.bonds;
    else if (selections.markets.includes('currencies')) multiplier *= aumModifiers.markets.currencies;
    else if (selections.markets.includes('commodities')) multiplier *= aumModifiers.markets.commodities;
    else if (selections.markets.includes('crypto')) multiplier *= aumModifiers.markets.crypto;
    
    // Apply investment approach modifier
    if (selections.investmentApproach.includes('quantitative')) {
      multiplier *= aumModifiers.investmentApproach.quantitative;
    } else if (selections.investmentApproach.includes('discretionary')) {
      multiplier *= aumModifiers.investmentApproach.discretionary;
    }
    
    // Apply timeframe modifier (use the longest timeframe selected)
    if (selections.investmentTimeframe.includes('long')) {
      multiplier *= aumModifiers.investmentTimeframe.long;
    } else if (selections.investmentTimeframe.includes('medium')) {
      multiplier *= aumModifiers.investmentTimeframe.medium;
    } else if (selections.investmentTimeframe.includes('short')) {
      multiplier *= aumModifiers.investmentTimeframe.short;
    }
      
    // If no market is selected, use a default value
    if (selections.markets.length === 0) {
      setAumAllocation(100); // Default $100M
      return;
    }
    
    // Get the selected market
    const selectedMarket = selections.markets[0];
    
    // Set AUM based on the selected market with type checking
    const marketValue = marketAumValues[selectedMarket as MarketKey] || 100;
    setAumAllocation(marketValue);
    
  }, [selections, baseAumAllocation]);

  // Effect to handle generalist sector logic
  useEffect(() => {
    if (isProcessing) return;
    
    // Get current selections
    const sectorSelections = [...selections.sectorFocus];
    const hasGeneralist = sectorSelections.includes('generalist');
    
    // Skip if no selections yet
    if (sectorSelections.length === 0) return;
    
    setIsProcessing(true);
    
    // Case 1: Generalist is selected, ensure all sectors are selected
    if (hasGeneralist) {
      // Get all sectors that should be selected
      const allSectors = ['generalist', ...actualSectorIds];
      
      // Check if all sectors are already selected
      if (!actualSectorIds.every(sector => sectorSelections.includes(sector))) {
        logger.debug('Generalist selected - selecting all sectors');
        setSelections(prev => ({
          ...prev,
          sectorFocus: allSectors
        }));
      }
    } 
    // Case 2: Not all sectors are selected, ensure generalist is not selected
    else if (sectorSelections.some(id => id !== 'generalist')) {
      // Check if all actual sectors are selected
      const allSectorsSelected = actualSectorIds.every(sector => 
        sectorSelections.includes(sector)
      );
      
      if (allSectorsSelected && !hasGeneralist) {
        // If all sectors are selected but generalist isn't, add generalist
        logger.debug('All sectors selected - adding generalist');
        setSelections(prev => ({
          ...prev,
          sectorFocus: [...prev.sectorFocus, 'generalist']
        }));
      }
    }
    
    setIsProcessing(false);
  }, [selections.sectorFocus, isProcessing]);

  // Custom handler for sector focus selection changes
  const handleSectorSelectionChange = (newValue: string[]) => {
    if (isProcessing) return;
    
    const currentSelections = selections.sectorFocus;
    const hasGeneralist = currentSelections.includes('generalist');
    const willHaveGeneralist = newValue.includes('generalist');
    
    // If generalist is being toggled
    if (hasGeneralist !== willHaveGeneralist) {
      if (willHaveGeneralist) {
        // Add all sectors when generalist is selected
        logger.debug('Generalist toggled on - adding all sectors');
        setSelections(prev => ({
          ...prev,
          sectorFocus: ['generalist', ...actualSectorIds]
        }));
      } else {
        // Remove generalist but keep other sectors
        logger.debug('Generalist toggled off - keeping selected sectors');
        setSelections(prev => ({
          ...prev,
          sectorFocus: prev.sectorFocus.filter(id => id !== 'generalist')
        }));
      }
      return;
    }
    
    // Check if any actual sector is being removed
    const currentActualSectors = currentSelections.filter(id => id !== 'generalist');
    const newActualSectors = newValue.filter(id => id !== 'generalist');
    
    if (currentActualSectors.length > newActualSectors.length && hasGeneralist) {
      // A sector was deselected while generalist was selected, remove generalist too
      logger.debug('Sector removed while generalist selected - removing generalist');
      setSelections(prev => ({
        ...prev,
        sectorFocus: newValue.filter(id => id !== 'generalist')
      }));
      return;
    }
    
    // Normal case - update selection as requested
    logger.debug('Normal sector selection update', { newValue });
    setSelections(prev => ({
      ...prev,
      sectorFocus: newValue
    }));
  };

  // Handle selection changes with proper typing for other categories
  const handleSelectionChange = (categoryId: string, newValue: string[]) => {
    if (categoryId === 'sectorFocus') {
      handleSectorSelectionChange(newValue);
    } else {
      logger.debug(`Selection changed for ${categoryId}`, { previous: selections[categoryId], new: newValue });
      setSelections(prev => ({
        ...prev,
        [categoryId]: newValue
      }));
    }
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Convert selections to parameters format
    const parameters = convertSelectionsToParameters();
    
    // Create book request
    const createBookRequest = {
      name: portfolioName,
      parameters: parameters
    };
    
    // Log form submission
    logger.info('Portfolio preferences form submitted', { 
      createBookRequest
    });
    
    // Check if all categories have at least one selection (except disabled ones)
    const requiredCategories = categories
      .filter(category => !category.disabled)
      .map(category => category.id);
    
    const isFormValid = requiredCategories.every(category => selections[category].length > 0);
    
    if (isFormValid) {
      try {
        // Show loading state
        setIsProcessing(true);
        
        // Create the book using the createBook function from context
        const result = await createBook(createBookRequest);
        
        if (result.success && result.bookId) {
          logger.info('Book created successfully', { bookId: result.bookId });
          
          // Show success message
          const toast = document.createElement('div');
          toast.textContent = 'Portfolio created successfully!';
          document.body.appendChild(toast);
          setTimeout(() => document.body.removeChild(toast), 3000);
          
          // Navigate to home page
          navigate('/home');
        } else {
          // Show error
          logger.error('Failed to create book', { error: result.error });
          alert('Failed to create portfolio: ' + (result.error || 'Unknown error'));
        }
      } catch (error) {
        logger.error('Exception during book creation', { error });
        alert('Error creating portfolio: ' + (error instanceof Error ? error.message : 'Unknown error'));
      } finally {
        setIsProcessing(false);
      }
    } else {
      logger.warn('Form validation failed - not all categories selected');
      alert('Please make selections in all required categories');
    }
  };

  return (
    <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <Button 
          startIcon={<ArrowBackIcon />} 
          onClick={handleBackToHome}
          variant="outlined"
          sx={{ mr: 2 }}
        >
          Back to Home
        </Button>
        <Typography variant="h4" component="h1">
          Portfolio Preferences
        </Typography>
      </Box>
      
      <Typography variant="body1" paragraph>
        Configure your preferences by selecting options in each category below.
      </Typography>
      
      <form onSubmit={handleSubmit}>
        {/* Portfolio Name Field */}
        <Paper sx={{ p: 3, mb: 4 }}>
          <TextField
            fullWidth
            label="Portfolio Name"
            variant="outlined"
            value={portfolioName}
            onChange={(e) => setPortfolioName(e.target.value)}
          />
        </Paper>

        {categories.map((category) => (
          <Paper key={category.id} sx={{ p: 3, mb: 4 }}>
            <Typography variant="h6" gutterBottom>
              {category.title}
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              {category.description}
            </Typography>
            
            {category.id === 'sectorFocus' ? (
              <Box sx={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: 1
              }}>
                {/* Generalist button - full width */}
                <Box sx={{ gridColumn: '1 / span 3', mb: 1 }}>
                  <ToggleButton
                    value="generalist"
                    selected={selections.sectorFocus.includes('generalist')}
                    onChange={() => {
                      const newValue = selections.sectorFocus.includes('generalist')
                        ? selections.sectorFocus.filter(id => id !== 'generalist')
                        : ['generalist', ...actualSectorIds];
                      handleSectorSelectionChange(newValue);
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
                    selected={selections.sectorFocus.includes(option.id)}
                    onChange={() => {
                      const currentSelections = [...selections.sectorFocus];
                      const newSelections = currentSelections.includes(option.id)
                        ? currentSelections.filter(id => id !== option.id)
                        : [...currentSelections, option.id];
                      handleSectorSelectionChange(newSelections);
                    }}
                    color="primary"
                    sx={{ height: '48px' }}
                  >
                    <Typography variant="body2">{option.label}</Typography>
                  </ToggleButton>
                ))}
              </Box>
            ) : (
              <ToggleButtonGroup
                value={selections[category.id]}
                onChange={(_, value) => {
                  // Ensure single select categories always have a value
                  if (!category.multiSelect && (!value || value.length === 0)) {
                    return;
                  }
                  handleSelectionChange(category.id, value as string[]);
                }}
                aria-label={category.title}
                color="primary"
                size="medium"
                fullWidth
                sx={{ mb: 1 }}
                {...(category.multiSelect ? { multiple: true } : {})}
                disabled={category.disabled}
              >
                {category.options.map((option) => (
                  <ToggleButton 
                    key={option.id} 
                    value={option.id}
                    aria-label={option.label}
                    disabled={category.disabled && option.id !== selections[category.id][0]}
                  >
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="body2">{option.label}</Typography>
                      {option.examples && (
                        <Typography variant="caption" color="text.secondary" display="block">
                          {option.examples}
                        </Typography>
                      )}
                    </Box>
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            )}
          </Paper>
        ))}
        
        <Paper sx={{ p: 3, mb: 4 }}>
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
          
        </Paper>
        
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            size="large"
            disabled={isProcessing}
          >
            {isProcessing ? 'Creating Portfolio...' : 'Generate Simulation'}
          </Button>
        </Box>
      </form>
    </Box>
  );
};

export default BookSetupPage;