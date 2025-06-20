// frontend_dist/book-app/src/pages/BookDetailsPage.tsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useConnection } from '../hooks/useConnection';
import { useToast } from '../hooks/useToast';
import { useBookManager } from '../hooks/useBookManager';
import { Book } from '@trading-app/types-core';
import ConvictionSubmissionContainer from '../components/Simulator/ConvictionSubmissionContainer';
import { Tabs, Tab } from '@mui/material';
import { 
  Box, 
  Button, 
  Card, 
  CardContent, 
  Typography, 
  Grid, 
  Chip,
  CircularProgress
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { config } from '@trading-app/config';

import './BookDetailsPage.css';

const BookDetailsPage: React.FC = () => {
  useRequireAuth();
  const { bookId } = useParams<{ bookId: string }>();
  const { isConnected, connectionManager, connectionState } = useConnection();
  const { addToast } = useToast();
  const bookManager = useBookManager();
  const navigate = useNavigate();

  const [book, setBook] = useState<Book | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isStartingSimulator, setIsStartingSimulator] = useState(false);
  const [activeTab, setActiveTab] = useState(0);

  // Get simulator status from connection state
  const simulatorStatus = connectionState?.simulatorStatus || 'UNKNOWN';
  const isSimulatorRunning = simulatorStatus === 'RUNNING';
  const isSimulatorBusy = simulatorStatus === 'STARTING' || simulatorStatus === 'STOPPING';

  useEffect(() => {
    const fetchBookDetails = async () => {
      if (!bookId) {
        addToast('error', 'Book ID is missing');
        handleBackToMain();
        return;
      }

      setIsLoading(true);
      
      try {
        const response = await bookManager.fetchBook(bookId);
        
        if (response.success && response.book) {
          setBook(response.book);
        } else {
          addToast('error', response.error || 'Book not found');
          handleBackToMain();
        }
      } catch (error: any) {
        console.error('Error fetching book details:', error);
        addToast('error', `Failed to load book details: ${error.message}`);
        handleBackToMain();
      } finally {
        setIsLoading(false);
      }
    };

    if (isConnected && bookId) {
      fetchBookDetails();
    }
  }, [bookId, isConnected, addToast, bookManager]);

  const handleBackToMain = () => {
    const mainAppUrl = config.gateway.baseUrl + '/app';
    window.location.href = `${mainAppUrl}`;
  };

  const handleStartSimulator = async () => {
    console.log('🎮 STEP 1: Starting simulator flow', {
      bookId,
      connectionManager: !!connectionManager,
      isConnected,
      simulatorStatus
    });
    
    if (!bookId || !connectionManager) {
      addToast('error', 'Cannot start simulator: Missing book ID or connection');
      return;
    }
    
    setIsStartingSimulator(true);
    
    try {
      console.log('🎮 STEP 2: Calling connectionManager.startSimulator()');
      const result = await connectionManager.startSimulator();
      console.log('🎮 STEP 3: Got result from startSimulator:', result);
      
      if (result.success) {
        addToast('success', 'Simulator started successfully');
        console.log('📡 Simulator started, navigating to dashboard');
        // Navigate to simulator page with bookId
        navigate(`/${bookId}/simulator/`);
      } else {
        addToast('error', `Failed to start simulator: ${result.error || 'Unknown error'}`);
        console.error('📡 Simulator start failed:', result);
      }
    } catch (error: any) {
      console.error('🎮 STEP ERROR: Exception in startSimulator:', error);
      addToast('error', `Error starting simulator: ${error.message}`);
    } finally {
      setIsStartingSimulator(false);
    }
  };

  // If simulator is already running for this book, show option to go to dashboard
  const handleGoToDashboard = () => {
    if (bookId) {
      navigate(`/${bookId}/simulator/`);
    }
  };

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <CircularProgress />
        <Typography variant="h6" sx={{ ml: 2 }}>Loading book details...</Typography>
      </Box>
    );
  }

  if (!book) {
    return (
      <Box sx={{ textAlign: 'center', p: 4 }}>
        <Typography variant="h5">Book not found</Typography>
        <Button variant="contained" onClick={handleBackToMain} sx={{ mt: 2 }}>
          Return to Main App
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto', p: { xs: 2, md: 4 } }}> 
      {/* Header with ONLY Back Button */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-start', alignItems: 'center', mb: 3 }}>
        <Button 
          startIcon={<ArrowBackIcon />} 
          variant="outlined" 
          onClick={handleBackToMain}
        >
          Back to Main App
        </Button>
      </Box>
            
      {/* Book Details Card - READ ONLY */}
      <Card 
        variant="outlined" 
        sx={{ 
          mb: 4,
          border: '1px solid #e5e7eb',
          borderRadius: 2
        }}
      >
        <CardContent sx={{ p: 0 }}>
          {/* Header */}
          <Box sx={{ 
            p: 3, 
            borderBottom: '1px solid #f3f4f6'
          }}>
            <Typography variant="h5" sx={{ fontWeight: 600, color: '#111827' }}>
              {book.name}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Trading Book - View Only
            </Typography>
          </Box>

          {/* Main Content - Horizontal Layout */}
          <Box sx={{ p: 3, size: 12 }}>
            <Grid container spacing={0}>
              {/* Regions */}
              <Grid {...{component: "div", item: true, xs: 12, md: 2, size: 2} as any} sx={{ pr: 4 }}>
                <Typography variant="subtitle2" sx={{ mb: 1, textAlign: 'center', color: '#6b7280', fontWeight: 600 }}>
                  Regions
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  {book.regions.map((region) => (
                    <Chip 
                      key={region.toUpperCase()}
                      label={region.toUpperCase()}
                      size="small"
                      sx={{
                        bgcolor: '#f9fafb',
                        color: '#374151',
                        border: '1px solid #e5e7eb',
                        fontSize: '0.75rem',
                        height: 20,
                        '& .MuiChip-label': { px: 1 }
                      }}
                    />
                  ))}
                </Box>
              </Grid>

              {/* Markets */}
              <Grid {...{component: "div", item: true, xs: 12, md: 2, size: 2} as any} sx={{ pr: 4 }}>
                <Typography variant="subtitle2" sx={{ mb: 1, textAlign: 'center', color: '#6b7280', fontWeight: 600 }}>
                  Markets
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  {book.markets.map((market) => (
                    <Chip 
                      key={market.toUpperCase()} 
                      label={market.toUpperCase()} 
                      size="small"
                      sx={{
                        bgcolor: '#f9fafb',
                        color: '#374151',
                        border: '1px solid #e5e7eb',
                        fontSize: '0.75rem',
                        height: 20,
                        '& .MuiChip-label': { px: 1 }
                      }}
                    />
                  ))}
                </Box>
              </Grid>

              {/* Instruments */}
              <Grid {...{component: "div", item: true, xs: 12, md: 2, size: 2} as any} sx={{ pr: 4 }}>
                <Typography variant="subtitle2" sx={{ mb: 1, textAlign: 'center', color: '#6b7280', fontWeight: 600 }}>
                  Instruments
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  {book.instruments.map((instrument) => (
                    <Chip 
                      key={instrument.toUpperCase()} 
                      label={instrument.toUpperCase()} 
                      size="small"
                      sx={{
                        bgcolor: '#f9fafb',
                        color: '#374151',
                        border: '1px solid #e5e7eb',
                        fontSize: '0.75rem',
                        height: 20,
                        '& .MuiChip-label': { px: 1 }
                      }}
                    />
                  ))}
                </Box>
              </Grid>

              {/* Investment Approach */}
              <Grid {...{component: "div", item: true, xs: 12, md: 2, size: 2} as any} sx={{ pr: 4 }}>
                <Typography variant="subtitle2" sx={{ mb: 1, textAlign: 'center', color: '#6b7280', fontWeight: 600 }}>
                  Approach
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  {book.investmentApproaches.map((approach) => (
                    <Chip 
                      key={approach.toUpperCase()} 
                      label={approach.toUpperCase()} 
                      size="small"
                      sx={{
                        bgcolor: '#f9fafb',
                        color: '#374151',
                        border: '1px solid #e5e7eb',
                        fontSize: '0.75rem',
                        height: 20,
                        '& .MuiChip-label': { px: 1 }
                      }}
                    />
                  ))}
                </Box>
              </Grid>

              {/* Position Types */}
              <Grid {...{component: "div", item: true, xs: 12, md: 2, size: 2} as any} sx={{ pr: 4 }}>
                <Typography variant="subtitle2" sx={{ mb: 1, textAlign: 'center', color: '#6b7280', fontWeight: 600 }}>
                  Position Types
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  {book.positionTypes.long && (
                    <Chip 
                      label="LONG" 
                      size="small"
                      sx={{
                        bgcolor: '#f9fafb',
                        color: '#374151',
                        border: '1px solid #e5e7eb',
                        fontSize: '0.75rem',
                        height: 20,
                        '& .MuiChip-label': { px: 1 }
                      }}
                    />
                  )}
                  {book.positionTypes.short && (
                    <Chip 
                      label="SHORT" 
                      size="small"
                      sx={{
                        bgcolor: '#f9fafb',
                        color: '#374151',
                        border: '1px solid #e5e7eb',
                        fontSize: '0.75rem',
                        height: 20,
                        '& .MuiChip-label': { px: 1 }
                      }}
                    />
                  )}
                </Box>
              </Grid>

              {/* Timeframe */}
              <Grid {...{component: "div", item: true, xs: 12, md: 2, size: 2} as any}>
                <Typography variant="subtitle2" sx={{ mb: 1, textAlign: 'center', color: '#6b7280', fontWeight: 600 }}>
                  Timeframe
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  {book.investmentTimeframes.map((timeframe) => (
                    <Chip 
                      key={timeframe.toUpperCase()} 
                      label={timeframe.toUpperCase()} 
                      size="small"
                      sx={{
                        bgcolor: '#f9fafb',
                        color: '#374151',
                        border: '1px solid #e5e7eb',
                        fontSize: '0.75rem',
                        height: 20,
                        '& .MuiChip-label': { px: 1 }
                      }}
                    />
                  ))}
                </Box>
              </Grid>
            </Grid>

            {/* Sectors Row - Only if exists */}
            {book.sectors && book.sectors.length > 0 && (
              <Box sx={{ mt: 3, pt: 3 }}>
                <Typography variant="subtitle2" sx={{ mb: 1, textAlign: 'center', color: '#6b7280', fontWeight: 600 }}>
                  Focus
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 0.5 }}>
                  {book.sectors.map((sector) => (
                    <Chip 
                      key={sector.toUpperCase()} 
                      label={sector.toUpperCase()} 
                      size="small"
                      sx={{
                        bgcolor: '#f9fafb',
                        color: '#374151',
                        border: '1px solid #e5e7eb',
                        fontSize: '0.75rem',
                        height: 20,
                        '& .MuiChip-label': { px: 1 }
                      }}
                    />
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Main Content Section */}
      <Card variant="outlined" sx={{ mb: 4 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs 
            value={activeTab} 
            onChange={(_, newValue) => setActiveTab(newValue)}
            variant="fullWidth"
            sx={{
              '& .MuiTab-root': {
                fontSize: '1.2rem',
                fontWeight: 600,
                textTransform: 'none',
                minHeight: 72,
                py: 2.5,
                transition: 'all 0.2s ease'
              },
              '& .Mui-selected': {
                fontWeight: 700,
                color: 'primary.main',
                backgroundColor: 'action.selected'
              },
              '& .MuiTabs-indicator': {
                height: 3,
                borderRadius: 1.5
              }
            }}
          >
            <Tab label="Start Simulator" />
            <Tab label="Conviction Management" />
          </Tabs>
        </Box>
        
        <CardContent sx={{ p: 0 }}>          
          {activeTab === 0 && (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              {/* Show different buttons based on simulator status */}
              {isSimulatorRunning ? (
                <Button 
                  variant="contained" 
                  color="success"
                  size="large"
                  startIcon={<PlayArrowIcon />}
                  onClick={handleGoToDashboard}
                  sx={{ 
                    py: 1.5, 
                    px: 4,
                    fontSize: '1.1rem',
                    borderRadius: 2
                  }}
                >
                  Go to Trading Dashboard
                </Button>
              ) : (
                <Button 
                  variant="contained" 
                  color="primary"
                  size="large"
                  startIcon={<PlayArrowIcon />}
                  onClick={handleStartSimulator}
                  disabled={isStartingSimulator || isSimulatorBusy || !isConnected}
                  sx={{ 
                    py: 1.5, 
                    px: 4,
                    fontSize: '1.1rem',
                    borderRadius: 2
                  }}
                >
                  {isStartingSimulator || isSimulatorBusy ? 'Starting Simulator...' : 'Start Simulator'}
                </Button>
              )}

              <Typography variant="body1" sx={{ mt: 3, maxWidth: 600, mx: 'auto' }}>
                {isSimulatorRunning 
                  ? 'Your trading simulator is running. Click above to access the dashboard.'
                  : 'Launch the simulator to begin trading with this book\'s settings. The simulator provides a real-time trading environment to test your convictions.'
                }
              </Typography>

              {/* Show simulator status */}
              <Typography variant="body2" sx={{ mt: 2, color: 'text.secondary' }}>
                Simulator Status: {simulatorStatus}
              </Typography>
            </Box>
          )}
          
          {activeTab === 1 && (
            <Box sx={{ p: 3 }}>
              <ConvictionSubmissionContainer />
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default BookDetailsPage;