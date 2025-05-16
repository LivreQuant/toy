// src/pages/EditBookPage.tsx
import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
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
  Grid,
  CircularProgress
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useToast } from '../hooks/useToast';
import { useBookManager } from '../hooks/useBookManager';
import { useConnection } from '../hooks/useConnection';
import { getLogger } from '../boot/logging';

// Initialize logger
const logger = getLogger('EditBookPage');

const EditBookPage: React.FC = () => {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const { isConnected } = useConnection();
  const { addToast } = useToast();
  const bookManager = useBookManager();
  
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  
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
  
  const actualSectorIds = sectors
    .filter(sector => sector.id !== 'generalist')
    .map(sector => sector.id);
  
  // Form state (similar to BookSetupPage.tsx)
  const [bookName, setBookName] = useState('');
  const [region, setRegion] = useState('us');
  const [selectedMarket, setSelectedMarket] = useState('equities');
  const [selectedInstrument, setSelectedInstrument] = useState('stocks');
  const [investmentApproaches, setInvestmentApproaches] = useState<string[]>([]);
  const [timeframes, setTimeframes] = useState<string[]>([]);
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [positionTypes, setPositionTypes] = useState<string[]>([]);
  const [initialCapital, setInitialCapital] = useState<number>(100);
  
  const steps = ['Basic Information', 'Investment Strategy', 'Investment Focus', 'Position & Capital'];
  
  // Fetch book details
  // src/pages/EditBookPage.tsx
    // In the useEffect hook where we fetch and process the book data:


    useEffect(() => {
        const fetchBookDetails = async () => {
          if (!bookId || !isConnected) return;
          
          setIsLoading(true);
          
          try {
            console.log(`Fetching book details for bookId: ${bookId}`);
            const response = await bookManager.fetchBook(bookId);
            
                  
            if (response.success && response.book) {
                const fetchedBook = response.book;
                console.log("Raw book data from API:", fetchedBook);
                
                // Check where parameters might be
                console.log("Parameters property:", fetchedBook.parameters);
                console.log("Complete book object keys:", Object.keys(fetchedBook));
                
                
              // Extract parameters
              let parameters: Array<[string, string, string]> = [];
              if (fetchedBook.parameters) {
                if (typeof fetchedBook.parameters === 'string') {
                  try {
                    parameters = JSON.parse(fetchedBook.parameters);
                  } catch (err) {
                    console.error("Failed to parse parameters string");
                  }
                } else if (Array.isArray(fetchedBook.parameters)) {
                  parameters = fetchedBook.parameters;
                }
              } else {
                // Look for parameters that might have been added directly to the book object
                const directProps = [
                  {cat: 'Region', sub: '', val: fetchedBook.region || ''},
                  {cat: 'Market', sub: '', val: fetchedBook.marketFocus || ''},
                  {cat: 'Instrument', sub: '', val: fetchedBook.instrument || ''},
                  {cat: 'Investment Approach', sub: '', val: fetchedBook.tradingStrategy || ''},
                  {cat: 'Allocation', sub: '', val: String(fetchedBook.initialCapital || 100)}
                ];
                
                // Convert any direct properties to parameters array format
                parameters = directProps
                  .filter(prop => prop.val)
                  .map(prop => [prop.cat, prop.sub, prop.val] as [string, string, string]);
                
                console.log("Reconstructed parameters from direct properties:", parameters);
              }
              
              // Set form state from book data
              setBookName(fetchedBook.name);
              
              // Log all parameters for debugging
              console.log("All parameters:", parameters);
              
              // Helper function to extract parameter value
              const getParameterValue = (category: string, subcategory: string = ""): string | null => {
                const param = parameters.find((p: any) => 
                  Array.isArray(p) && p[0] === category && (subcategory === "" || p[1] === subcategory)
                );
                
                console.log(`Looking for parameter ${category}${subcategory ? `-${subcategory}` : ''}, found:`, param);
                return param ? param[2] : null;
              };
              
              // Helper function to find all parameters with a specific category
              const getParameterValues = (category: string): string[] => {
                const values = parameters
                  .filter((p: any) => Array.isArray(p) && p[0] === category)
                  .map((p: any) => p[2]);
                
                console.log(`Found ${values.length} values for category ${category}:`, values);
                return values;
              };
              
              // Region
              const regionValue = getParameterValue('Region');
              if (regionValue) {
                console.log(`Setting region to: ${regionValue}`);
                setRegion(regionValue);
              }
              
              // Market
              const marketValue = getParameterValue('Market');
              if (marketValue) {
                console.log(`Setting market to: ${marketValue}`);
                setSelectedMarket(marketValue);
              }
              
              // Instrument
              const instrumentValue = getParameterValue('Instrument');
              if (instrumentValue) {
                console.log(`Setting instrument to: ${instrumentValue}`);
                setSelectedInstrument(instrumentValue);
              }
              
              // Investment approaches
              const approachValues = getParameterValues('Investment Approach');
              console.log(`Setting investment approaches to:`, approachValues);
              setInvestmentApproaches(approachValues);
              
              // Timeframes
              const timeframeValues = getParameterValues('Investment Timeframe');
              console.log(`Setting timeframes to:`, timeframeValues);
              setTimeframes(timeframeValues);
              
              // Sectors
              const sectorValues = getParameterValues('Sector');
              if (sectorValues.length > 0) {
                const allSectorsSelected = actualSectorIds.every(id => 
                  sectorValues.includes(id)
                );
                
                let updatedSectors = [...sectorValues];
                if (allSectorsSelected && !updatedSectors.includes('generalist')) {
                  updatedSectors.push('generalist');
                }
                
                console.log(`Setting sectors to:`, updatedSectors);
                setSelectedSectors(updatedSectors);
              }
              
              // Position Types
              const longPosition = getParameterValue('Position', 'Long') === 'true';
              const shortPosition = getParameterValue('Position', 'Short') === 'true';
              
              const positions = [];
              if (longPosition) positions.push('long');
              if (shortPosition) positions.push('short');
              console.log(`Setting position types to:`, positions);
              setPositionTypes(positions);
              
              // Initial Capital
              const capitalValue = getParameterValue('Allocation');
              if (capitalValue) {
                const capital = parseFloat(capitalValue);
                if (!isNaN(capital)) {
                  console.log(`Setting initial capital to: ${capital}`);
                  setInitialCapital(capital);
                }
              }
              
              // Log final state values to verify
              setTimeout(() => {
                console.log("Final state values after processing:");
                console.log("Region:", region);
                console.log("Market:", selectedMarket);
                console.log("Instrument:", selectedInstrument);
                console.log("Investment Approaches:", investmentApproaches);
                console.log("Timeframes:", timeframes);
                console.log("Sectors:", selectedSectors);
                console.log("Position Types:", positionTypes);
                console.log("Initial Capital:", initialCapital);
              }, 100);
              
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
  
  // Validation functions (similar to BookSetupPage.tsx)
  const validateCurrentStep = () => {
    const newErrors: Record<string, string> = {};
    
    switch (activeStep) {
      case 0: // Basic Information
        if (!bookName.trim()) {
          newErrors.bookName = 'Book name is required';
        }
        break;
        
      case 1: // Investment Strategy
        if (investmentApproaches.length === 0) {
          newErrors.investmentApproach = 'Please select at least one investment approach';
        }
        if (timeframes.length === 0) {
          newErrors.timeframes = 'Please select at least one investment timeframe';
        }
        break;
        
      case 2: // Sector Focus
        if (selectedSectors.length === 0) {
          newErrors.sectors = 'Please select at least one sector';
        }
        break;
        
      case 3: // Position & Capital
        if (positionTypes.length === 0) {
          newErrors.positions = 'Please select at least one position type';
        }
        if (!initialCapital || initialCapital <= 0) {
          newErrors.initialCapital = 'Please enter a valid initial capital amount';
        }
        break;
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  // Prepare form data for submission
  const prepareFormData = () => {
    const parameters: Array<[string, string, string]> = [
      ["Region", "", region],
      ["Market", "", selectedMarket],
      ["Instrument", "", selectedInstrument]
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
    
    // Add allocation (convert to millions for display)
    parameters.push(["Allocation", "", initialCapital.toString()]);
    
    return {
      name: bookName,
      parameters
    };
  };
  
  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!bookId) {
      addToast('error', 'No book ID found');
      return;
    }
    
    // Final validation
    if (!validateCurrentStep()) {
      return;
    }
    
    setIsProcessing(true);
    
    try {
      const formData = prepareFormData();
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
  
  // Render basic information step
  const renderBasicInformation = () => (
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
        <Typography variant="h6" gutterBottom>
          Region
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Geographic focus of the investment strategy
        </Typography>
        
        <ToggleButtonGroup
          value={region}
          exclusive
          onChange={(_, value) => value && setRegion(value)}
          aria-label="Region"
          color="primary"
          fullWidth
        >
          <ToggleButton value="us">
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2">US Region</Typography>
            </Box>
          </ToggleButton>
          <ToggleButton value="eu" disabled>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2">EU Region</Typography>
              <Typography variant="caption" color="text.secondary" display="block">
                Coming soon
              </Typography>
            </Box>
          </ToggleButton>
          <ToggleButton value="asia" disabled>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2">Asia Region</Typography>
              <Typography variant="caption" color="text.secondary" display="block">
                Coming soon
              </Typography>
            </Box>
          </ToggleButton>
          <ToggleButton value="emerging" disabled>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2">Emerging</Typography>
              <Typography variant="caption" color="text.secondary" display="block">
                Coming soon
              </Typography>
            </Box>
          </ToggleButton>
        </ToggleButtonGroup>
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="h6" gutterBottom>
          Markets
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          The markets accessed by the investment strategy
        </Typography>
        
        <ToggleButtonGroup
          value={selectedMarket}
          exclusive
          onChange={(_, value) => value && setSelectedMarket(value)}
          aria-label="Markets"
          color="primary"
          fullWidth
        >
          <ToggleButton value="equities">
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2">Equities</Typography>
            </Box>
          </ToggleButton>
          <ToggleButton value="bonds" disabled>
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
      
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="h6" gutterBottom>
          Instruments
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Financial instruments used in the portfolio
        </Typography>
        
        <ToggleButtonGroup
          value={selectedInstrument}
          exclusive
          onChange={(_, value) => value && setSelectedInstrument(value)}
          aria-label="Instruments"
          color="primary"
          fullWidth
        >
          <ToggleButton value="stocks">
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="body2">Stocks</Typography>
            </Box>
          </ToggleButton>
          <ToggleButton value="etfs" disabled>
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
  
  // Render investment strategy step
  const renderInvestmentStrategy = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="h6" gutterBottom>
          Investment Approach
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          The fundamental methodology used to make investment decisions
        </Typography>
        
        <ToggleButtonGroup
            value={investmentApproaches}
            onChange={(_, value) => {
                console.log("New investment approaches value:", value);
                setInvestmentApproaches(value || []);
            }}
            aria-label="Investment Approach"
            color="primary"
            fullWidth
            >
            <ToggleButton value="quantitative">
                <Box sx={{ textAlign: 'center' }}>
                <Typography variant="body2">
                    Quantitative {investmentApproaches.includes('quantitative') ? '(Selected)' : ''}
                </Typography>
                </Box>
            </ToggleButton>
            <ToggleButton value="discretionary">
                <Box sx={{ textAlign: 'center' }}>
                <Typography variant="body2">
                    Discretionary {investmentApproaches.includes('discretionary') ? '(Selected)' : ''}
                </Typography>
                </Box>
            </ToggleButton>
        </ToggleButtonGroup>
        {errors.investmentApproach && (
          <Typography color="error" variant="caption">{errors.investmentApproach}</Typography>
        )}
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="h6" gutterBottom>
          Investment Timeframe
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          The typical holding period for positions in the portfolio
        </Typography>
        
        <ToggleButtonGroup
        value={timeframes}
        onChange={(_, value) => setTimeframes(value || [])} // Handle null value
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
        {errors.timeframes && (
          <Typography color="error" variant="caption">{errors.timeframes}</Typography>
        )}
      </Grid>
    </Grid>
  );
  
  // Render sector focus step
  const renderSectorFocus = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12} as any}>
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
              onClick={() => handleSectorToggle('generalist')}
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
              onClick={() => handleSectorToggle(option.id)}
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
  
  // Render position and capital step
  const renderPositionAndCapital = () => (
    <Grid container spacing={3}>
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="h6" gutterBottom>
          Position Types
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          The directional exposure strategy employed in the portfolio
        </Typography>
        
        <ToggleButtonGroup
        value={positionTypes}
        onChange={(_, value) => setPositionTypes(value || [])} // Handle null value
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
        {errors.positions && (
          <Typography color="error" variant="caption">{errors.positions}</Typography>
        )}
      </Grid>
      
      <Grid {...{component: "div", item: true, xs: 12} as any}>
        <Typography variant="h6" gutterBottom>
          Allocation
        </Typography>
        <Typography variant="body2" color="text.secondary" paragraph>
          Specify the managed allocation (in millions USD).
        </Typography>
        
        <FormControl fullWidth sx={{ mb: 3 }}>
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
                  onChange={(e) => setInitialCapital(Number((e.target as HTMLInputElement).value))}
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
            <FormHelperText error>{errors.initialCapital}</FormHelperText>
          )}
        </FormControl>
      </Grid>
    </Grid>
  );
  
  // Render step content
  const renderStepContent = (step: number) => {
    switch (step) {
      case 0:
        return renderBasicInformation();
      case 1:
        return renderInvestmentStrategy();
      case 2:
        return renderSectorFocus();
      case 3:
        return renderPositionAndCapital();
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
  
  return (
    <Box sx={{ p: 4, maxWidth: 900, mx: 'auto' }}>
      <Button 
        startIcon={<ArrowBackIcon />} 
        onClick={handleGoBack}
        variant="outlined"
        sx={{ mr: 2, mb: 4 }}
      >
        Back to Home
      </Button>
      
      <Paper elevation={3} sx={{ p: 4 }}>
        <Typography variant="h4" component="h1" align="center" gutterBottom>
          Edit Book
        </Typography>
        
        <Typography variant="subtitle1" color="text.secondary" align="center" paragraph>
          Update your book's preferences step by step
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
              {isProcessing ? (
                <>
                  <CircularProgress size={24} sx={{ mr: 1 }} />
                  Updating Book...
                </>
              ) : (
                'Update Book'
              )}
            </Button>
          )}
        </Box>
      </form>
    </Paper>
  </Box>
);
};

export default EditBookPage;