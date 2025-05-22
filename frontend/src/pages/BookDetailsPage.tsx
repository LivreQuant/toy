// src/pages/BookDetailsPage.tsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useConnection } from '../hooks/useConnection';
import { useToast } from '../hooks/useToast';
import { useBookManager } from '../hooks/useBookManager';
import { Book } from '../types';
import OrderSubmissionContainer from '../components/Simulator/OrderSubmissionContainer';

import { Tabs, Tab } from '@mui/material';


import { 
  Box, 
  Button, 
  Card, 
  CardContent, 
  Typography, 
  Grid, 
  Divider, 
  Paper, 
  Chip,
  CircularProgress
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';

import './BookDetailsPage.css';

const BookDetailsPage: React.FC = () => {
  useRequireAuth();
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const { isConnected, connectionManager } = useConnection();
  const { addToast } = useToast();
  const bookManager = useBookManager();

  const [book, setBook] = useState<Book | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isStartingSimulator, setIsStartingSimulator] = useState(false);

  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => {
    const fetchBookDetails = async () => {
      if (!bookId) {
        addToast('error', 'Book ID is missing');
        navigate('/home');
        return;
      }

      setIsLoading(true);
      
      try {
        // Use the fetchBook method from BookManager
        const response = await bookManager.fetchBook(bookId);
        
        if (response.success && response.book) {
          setBook(response.book);
        } else {
          addToast('error', response.error || 'Book not found');
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

    if (isConnected && bookId) {
      fetchBookDetails();
    }
  }, [bookId, isConnected, navigate, addToast, bookManager]);

  const handleBack = () => {
    navigate('/home');
  };

  const handleStartSimulator = async () => {
    if (!bookId || !connectionManager) return;
    
    setIsStartingSimulator(true);
    
    try {
      const result = await connectionManager.startSimulator();
      
      if (result.success) {
        addToast('success', 'Simulator started successfully');
        navigate(`/simulator/${bookId}`);
      } else {
        addToast('error', `Failed to start simulator: ${result.error || 'Unknown error'}`);
      }
    } catch (error: any) {
      addToast('error', `Error starting simulator: ${error.message}`);
    } finally {
      setIsStartingSimulator(false);
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
        <Button variant="contained" onClick={handleBack} sx={{ mt: 2 }}>
          Return to Home
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ maxWidth: 1200, mx: 'auto', p: { xs: 2, md: 4 } }}>
      {/* Header with Back Button and Edit Button */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Button 
          startIcon={<ArrowBackIcon />} 
          variant="outlined" 
          onClick={handleBack}
        >
          Back to Home
        </Button>
        
        <Button
          variant="contained"
          color="primary"
          startIcon={<EditIcon />}
          onClick={() => navigate(`/books/${bookId}/edit`)}
        >
          Edit Book
        </Button>
      </Box>
            
      {/* Book Details Card - Clean Horizontal Layout */}
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
      

      {/* Order Management Section - Always accessible */}
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
            <Tab 
              label="Start Simulator" 
            />
            <Tab 
              label="Conviction Management" 
            />
          </Tabs>
        </Box>
        
        <CardContent>
          {activeTab === 0 && (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Button 
                variant="contained" 
                color="primary"
                size="large"
                startIcon={<PlayArrowIcon />}
                onClick={handleStartSimulator}
                disabled={isStartingSimulator || !isConnected}
                sx={{ 
                  py: 1.5, 
                  px: 4,
                  fontSize: '1.1rem',
                  borderRadius: 2
                }}
              >
                {isStartingSimulator ? 'Starting Simulator...' : 'Start Simulator'}
              </Button>

              <Typography variant="body1" sx={{ mt: 3, maxWidth: 600, mx: 'auto' }}>
                Launch the simulator to begin trading with this book's settings. 
                The simulator provides a real-time trading environment to test your convictions.
              </Typography>
            </Box>
          )}
          
          {activeTab === 1 && (
            <OrderSubmissionContainer />
          )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default BookDetailsPage;