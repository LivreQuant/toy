// src/pages/EditBookPage.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { 
  Box, 
  Button, 
  Typography, 
  Paper, 
  Stepper, 
  Step, 
  StepLabel,
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  ToggleButton,
  ToggleButtonGroup,
  TextField,
  FormHelperText,
  Grid,
  CircularProgress,
  Alert
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { Book } from '../types';
import { useToast } from '../hooks/useToast';
import { useBookManager } from '../hooks/useBookManager';
import { useConnection } from '../hooks/useConnection';

const EditBookPage: React.FC = () => {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const { isConnected } = useConnection();
  const { addToast } = useToast();
  const bookManager = useBookManager();
  
  const [isLoading, setIsLoading] = useState(true);
  const [book, setBook] = useState<Book | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  
  // Form state
  const [bookName, setBookName] = useState('');
  const [initialCapital, setInitialCapital] = useState<number>(100);
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [selectedMarket, setSelectedMarket] = useState('equities');
  const [selectedInstrument, setSelectedInstrument] = useState('stocks');
  const [investmentApproaches, setInvestmentApproaches] = useState<string[]>([]);
  const [timeframes, setTimeframes] = useState<string[]>([]);
  const [positionTypes, setPositionTypes] = useState<string[]>([]);
  const [region, setRegion] = useState('us');
  
  const steps = ['Book Information', 'Market Focus', 'Investment Approach'];
  
  // Sectors
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
  
  // Helper function to extract parameter value
  const getParameterValue = (parameters: any[], category: string, subcategory: string = ""): string | null => {
    if (!parameters) return null;
    
    // Find the parameter that matches the category and subcategory
    const param = parameters.find((p: any) => 
      Array.isArray(p) && p[0] === category && p[1] === subcategory
    );
    
    return param ? param[2] : null;
  };
  
  // Helper function to find all parameters with a specific category
  const getParameterValues = (parameters: any[], category: string): string[] => {
    if (!parameters) return [];
    
    return parameters
      .filter((p: any) => Array.isArray(p) && p[0] === category)
      .map((p: any) => p[2]);
  };
  
  // Fetch book details
  useEffect(() => {
    const fetchBookDetails = async () => {
      if (!bookId || !isConnected) return;
      
      setIsLoading(true);
      
      try {
        const response = await bookManager.fetchBook(bookId);
        
        if (response.success && response.book) {
          const fetchedBook = response.book;
          setBook(fetchedBook);
          
          // Extract parameters
          const parameters = fetchedBook.parameters 
            ? (Array.isArray(fetchedBook.parameters) ? fetchedBook.parameters : JSON.parse(fetchedBook.parameters))
            : [];
          
          // Set form state from book data
          setBookName(fetchedBook.name);
          
          // Get initial capital
          const capitalValue = getParameterValue(parameters, 'Allocation');
          setInitialCapital(capitalValue ? parseFloat(capitalValue) : 100);
          
          // Get market
          const marketValue = getParameterValue(parameters, 'Market');
          if (marketValue) setSelectedMarket(marketValue);
          
          // Get instrument
          const instrumentValue = getParameterValue(parameters, 'Instrument');
          if (instrumentValue) setSelectedInstrument(instrumentValue);
          
          // Get region
          const regionValue = getParameterValue(parameters, 'Region');
          if (regionValue) setRegion(regionValue);
          
          // Get sectors
          const sectorValues = getParameterValues(parameters, 'Sector');
          if (sectorValues.length > 0) {
            setSelectedSectors(sectorValues);
            
            // Check if all sectors are selected
            const allSectorsSelected = actualSectorIds.every(id => sectorValues.includes(id));
            if (allSectorsSelected && !sectorValues.includes('generalist')) {
              setSelectedSectors([...sectorValues, 'generalist']);
            }
          }
          
          // Get investment approaches
          const approachValues = getParameterValues(parameters, 'Investment Approach');
          if (approachValues.length > 0) {
            setInvestmentApproaches(approachValues);
          }
          
          // Get timeframes
          const timeframeValues = getParameterValues(parameters, 'Investment Timeframe');
          if (timeframeValues.length > 0) {
            setTimeframes(timeframeValues);
          }
          
          // Get position types
          const longPosition = getParameterValue(parameters, 'Position', 'Long') === 'true';
          const shortPosition = getParameterValue(parameters, 'Position', 'Short') === 'true';
          
          const positions = [];
          if (longPosition) positions.push('long');
          if (shortPosition) positions.push('short');
          setPositionTypes(positions);
          
        } else {
          addToast('error', response.error || 'Failed to fetch book details');
          navigate('/home');
        }
      } catch (error: any) {
        console.error('Error fetching book details:', error);
        addToast('error', `Failed to load book details: ${error.message}`);
        navigate('/home');
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchBookDetails();
  }, [bookId, isConnected, bookManager, addToast, navigate]);
  
  const handleNext = () => {
    let isValid = false;
    
    // Validate current step
    switch (activeStep) {
      case 0: // Book Info
        isValid = validateBookInfo();
        break;
      case 1: // Market Focus
        isValid = validateMarketFocus();
        break;
      case 2: // Investment Approach
        isValid = validateInvestmentApproach();
        break;
      default:
        isValid = true;
    }
    
    if (isValid) {
      setActiveStep((prevStep) => prevStep + 1);
    }
  };
  
  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };
  
  const handleBackToHome = () => {
    navigate('/home');
  };
  
  // Validation functions
  const validateBookInfo = () => {
    const newErrors: Record<string, string> = {};
    
    if (!bookName.trim()) {
      newErrors.bookName = 'Book name is required';
    }
    
    if (initialCapital <= 0) {
      newErrors.initialCapital = 'Initial capital must be greater than 0';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const validateMarketFocus = () => {
    const newErrors: Record<string, string> = {};
    
    if (!selectedMarket) {
      newErrors.market = 'Market is required';
    }
    
    if (!selectedInstrument) {
      newErrors.instrument = 'Instrument is required';
    }
    
    if (selectedSectors.length === 0) {
      newErrors.sectors = 'At least one sector must be selected';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const validateInvestmentApproach = () => {
    const newErrors: Record<string, string> = {};
    
    if (investmentApproaches.length === 0) {
      newErrors.approaches = 'At least one investment approach is required';
    }
    
    if (timeframes.length === 0) {
      newErrors.timeframes = 'At least one investment timeframe is required';
    }
    
    if (positionTypes.length === 0) {
      newErrors.positions = 'At least one position type is required';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  // Sector selection handler
  const handleSectorSelectionChange = (newSectors: string[]) => {
    const currentSelections = selectedSectors;
    const hasGeneralist = currentSelections.includes('generalist');
    const willHaveGeneralist = newSectors.includes('generalist');
    
    // If generalist is being toggled
    if (hasGeneralist !== willHaveGeneralist) {
      if (willHaveGeneralist) {
        // Add all sectors when generalist is selected
        setSelectedSectors(['generalist', ...actualSectorIds]);
      } else {
        // Remove generalist but keep other sectors
        setSelectedSectors(newSectors.filter(id => id !== 'generalist'));
      }
      return;
    }
    
    // Check if any actual sector is being removed
    const currentActualSectors = currentSelections.filter(id => id !== 'generalist');
    const newActualSectors = newSectors.filter(id => id !== 'generalist');
    
    if (currentActualSectors.length > newActualSectors.length && hasGeneralist) {
      // A sector was deselected while generalist was selected, remove generalist too
      setSelectedSectors(newSectors.filter(id => id !== 'generalist'));
      return;
    }
    
    // Normal case - update selection as requested
    setSelectedSectors(newSectors);
  };
  
  // Sector toggle handler
  const handleSectorToggle = (sector: string) => {
    const currentSelections = [...selectedSectors];
    const sectorIndex = currentSelections.indexOf(sector);
    
    if (sector === 'generalist') {
      if (sectorIndex === -1) {
        // Adding generalist - add all sectors
        setSelectedSectors(['generalist', ...actualSectorIds]);
      } else {
        // Removing generalist - keep only selected sectors without generalist
        setSelectedSectors(currentSelections.filter(id => id !== 'generalist'));
      }
    } else {
      if (sectorIndex === -1) {
        // Adding a sector
        const newSelections = [...currentSelections, sector];
        
        // Check if all sectors are now selected
        const allSectorsSelected = actualSectorIds.every(id => 
          id === sector || currentSelections.includes(id)
        );
        
        if (allSectorsSelected) {
          // All sectors selected, add generalist too
          setSelectedSectors([...newSelections, 'generalist']);
        } else {
          setSelectedSectors(newSelections);
        }
      } else {
        // Removing a sector - remove generalist too if it's selected
        const newSelections = currentSelections.filter(id => id !== sector);
        if (currentSelections.includes('generalist')) {
          newSelections.splice(newSelections.indexOf('generalist'), 1);
        }
        setSelectedSectors(newSelections);
      }
    }
  };
  
  // Prepare form data for submission
  const prepareFormData = () => {
    const parameters: Array<[string, string, string]> = [
      ["Allocation", "", initialCapital.toString()],
      ["Instrument", "", selectedInstrument],
      ["Market", "", selectedMarket],
      ["Region", "", region]
    ];
    
    // Add investment approaches
    investmentApproaches.forEach(approach => {
      parameters.push(["Investment Approach", "", approach]);
    });
    
    // Add timeframes
    timeframes.forEach(timeframe => {
      parameters.push(["Investment Timeframe", "", timeframe]);
    });
    
    // Add sectors (excluding generalist to avoid duplication)
    selectedSectors
      .filter(sector => sector !== 'generalist')
      .forEach(sector => {
        parameters.push(["Sector", "", sector]);
      });
    
    // Add position types
    parameters.push(["Position", "Long", positionTypes.includes('long').toString()]);
    parameters.push(["Position", "Short", positionTypes.includes('short').toString()]);
    
    return {
      name: bookName,
      parameters
    };
  };
  
  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!bookId || !book) {
      addToast('error', 'No book found to update');
      return;
    }
    
    // Validate current step before submitting
    let isValid = false;
    switch (activeStep) {
      case 0: // Book Info
        isValid = validateBookInfo();
        break;
      case 1: // Market Focus
        isValid = validateMarketFocus();
        break;
      case 2: // Investment Approach
        isValid = validateInvestmentApproach();
        break;
      default:
        isValid = true;
    }
    
    if (!isValid) return;
    
    setIsProcessing(true);
    
    const formData = prepareFormData();
    
    try {
      // Add updateBook method to BookManager
      const response = await bookManager.updateBook(bookId, formData);
      
      if (response.success) {
        addToast('success', 'Book updated successfully!');
        navigate(`/books/${bookId}`);
      } else {
        addToast('error', response.error || 'Failed to update book');
      }
    } catch (error: any) {
      console.error('Error updating book:', error);
      addToast('error', `Error updating book: ${error.message}`);
    } finally {
      setIsProcessing(false);
    }
  };
  
  // Render book information form
  const renderBookInfo = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <TextField
          required
          fullWidth
          label="Book Name"
          value={bookName}
          onChange={(e) => setBookName(e.target.value)}
          error={!!errors.bookName}
          helperText={errors.bookName}
        />
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="subtitle1" gutterBottom>
          Initial Capital
        </Typography>
        <FormControl fullWidth error={!!errors.initialCapital}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Box sx={{ flexGrow: 1 }}>
              <Typography id="capital-slider" gutterBottom>
                ${initialCapital.toLocaleString()}
              </Typography>
              <Box sx={{ px: 2 }}>
                <Box
                  component="input"
                  type="range"
                  min={50}
                  max={1000}
                  step={50}
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(Number(e.target.value))}
                  sx={{ width: '100%' }}
                />
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                  <Typography variant="caption">$50M</Typography>
                  <Typography variant="caption">$500M</Typography>
                  <Typography variant="caption">$1000M</Typography>
                </Box>
              </Box>
            </Box>
            <TextField
              value={initialCapital}
              onChange={(e) => {
                const value = parseInt(e.target.value);
                if (!isNaN(value) && value > 0) {
                  setInitialCapital(value);
                }
              }}
              type="number"
              InputProps={{ inputProps: { min: 50, max: 1000 } }}
              sx={{ width: 100 }}
            />
          </Box>
          {errors.initialCapital && (
            <FormHelperText>{errors.initialCapital}</FormHelperText>
          )}
        </FormControl>
      </Grid>
    </Grid>
  );
  
  // Render market focus form
  const renderMarketFocus = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
        <Typography variant="subtitle1" gutterBottom>
          Market
        </Typography>
        <ToggleButtonGroup
          value={selectedMarket}
          exclusive
          onChange={(_, value) => value && setSelectedMarket(value)}
          fullWidth
          sx={{ mb: 2 }}
        >
          <ToggleButton value="equities">Equities</ToggleButton>
          <ToggleButton value="bonds" disabled>Bonds</ToggleButton>
          <ToggleButton value="currencies" disabled>Currencies</ToggleButton>
          <ToggleButton value="commodities" disabled>Commodities</ToggleButton>
        </ToggleButtonGroup>
        {errors.market && (
          <Typography color="error" variant="caption">{errors.market}</Typography>
        )}
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
        <Typography variant="subtitle1" gutterBottom>
          Instruments
        </Typography>
        <ToggleButtonGroup
          value={selectedInstrument}
          exclusive
          onChange={(_, value) => value && setSelectedInstrument(value)}
          fullWidth
          sx={{ mb: 2 }}
        >
          <ToggleButton value="stocks">Stocks</ToggleButton>
          <ToggleButton value="etfs" disabled>ETFs</ToggleButton>
          <ToggleButton value="options" disabled>Options</ToggleButton>
        </ToggleButtonGroup>
        {errors.instrument && (
          <Typography color="error" variant="caption">{errors.instrument}</Typography>
        )}
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="subtitle1" gutterBottom>
          Region
        </Typography>
        <ToggleButtonGroup
          value={region}
          exclusive
          onChange={(_, value) => value && setRegion(value)}
          fullWidth
          sx={{ mb: 2 }}
        >
          <ToggleButton value="us">US</ToggleButton>
          <ToggleButton value="eu" disabled>Europe</ToggleButton>
          <ToggleButton value="asia" disabled>Asia</ToggleButton>
          <ToggleButton value="global" disabled>Global</ToggleButton>
        </ToggleButtonGroup>
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="subtitle1" gutterBottom>
          Sector Focus
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
              onChange={() => handleSectorToggle('generalist')}
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
          {sectors.filter(s => s.id !== 'generalist').map((sector) => (
            <ToggleButton 
              key={sector.id} 
              value={sector.id}
              selected={selectedSectors.includes(sector.id)}
              onChange={() => handleSectorToggle(sector.id)}
              color="primary"
              sx={{ height: '48px' }}
            >
              <Typography variant="body2">{sector.label}</Typography>
            </ToggleButton>
          ))}
        </Box>
        {errors.sectors && (
          <Typography color="error" variant="caption">{errors.sectors}</Typography>
        )}
      </Grid>
    </Grid>
  );
  
  // Render investment approach form
  const renderInvestmentApproach = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="subtitle1" gutterBottom>
          Investment Approach
        </Typography>
        <ToggleButtonGroup
          value={investmentApproaches}
          onChange={(_, value) => setInvestmentApproaches(value)}
          aria-label="Investment Approach"
          fullWidth
          sx={{ mb: 2 }}
        >
          <ToggleButton value="quantitative">Quantitative</ToggleButton>
          <ToggleButton value="discretionary">Discretionary</ToggleButton>
        </ToggleButtonGroup>
        {errors.approaches && (
          <Typography color="error" variant="caption">{errors.approaches}</Typography>
        )}
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="subtitle1" gutterBottom>
          Investment Timeframe
        </Typography>
        <ToggleButtonGroup
          value={timeframes}
          onChange={(_, value) => setTimeframes(value)}
          aria-label="Investment Timeframe"
          fullWidth
          sx={{ mb: 2 }}
        >
          <ToggleButton value="short">Short-term</ToggleButton>
          <ToggleButton value="medium">Medium-term</ToggleButton>
          <ToggleButton value="long">Long-term</ToggleButton>
        </ToggleButtonGroup>
        {errors.timeframes && (
          <Typography color="error" variant="caption">{errors.timeframes}</Typography>
        )}
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="subtitle1" gutterBottom>
          Position Types
        </Typography>
        <ToggleButtonGroup
          value={positionTypes}
          onChange={(_, value) => setPositionTypes(value)}
          aria-label="Position Types"
          fullWidth
          sx={{ mb: 2 }}
        >
          <ToggleButton value="long">Long</ToggleButton>
          <ToggleButton value="short">Short</ToggleButton>
        </ToggleButtonGroup>
        {errors.positions && (
          <Typography color="error" variant="caption">{errors.positions}</Typography>
        )}
      </Grid>
    </Grid>
  );
  
  // Render the appropriate step content
  const renderStepContent = (step: number) => {
    switch (step) {
      case 0:
        return renderBookInfo();
      case 1:
        return renderMarketFocus();
      case 2:
        return renderInvestmentApproach();
      default:
        return null;
    }
  };
  
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '300px' }}>
        <CircularProgress />
        <Typography variant="h6" sx={{ ml: 2 }}>
          Loading book details...
        </Typography>
      </Box>
    );
  }
  
  if (!book) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">Book not found or could not be loaded.</Alert>
        <Button 
          startIcon={<ArrowBackIcon />}
          onClick={handleBackToHome}
          variant="contained"
          sx={{ mt: 2 }}
        >
          Back to Home
        </Button>
      </Box>
    );
  }
  
  return (
    <Box sx={{ p: 4, maxWidth: 900, mx: 'auto' }}>
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
          Edit Book
        </Typography>
      </Box>
      
      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h5" component="h2" align="center" gutterBottom>
          Update "{book.name}"
        </Typography>
        
        <Stepper activeStep={activeStep} sx={{ mb: 4, pt: 2, pb: 4 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>
        
        <Divider sx={{ mb: 4 }} />
        
        <form onSubmit={handleSubmit}>
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
                type="submit"
                disabled={isProcessing}
              >
                {isProcessing ? 'Updating Book...' : 'Update Book'}
              </Button>
            )}
          </Box>
        </form>
      </Paper>
    </Box>
  );
};

export default EditBookPage;