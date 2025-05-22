// src/pages/BookDetailsPage.tsx
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useConnection } from '../hooks/useConnection';
import { useToast } from '../hooks/useToast';
import { useBookManager } from '../hooks/useBookManager';
import { Book } from '../types';
import OrderSubmissionContainer from '../components/Simulator/OrderSubmissionContainer';


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
      
      {/* Book Title */}
      <Typography variant="h4" component="h1" gutterBottom>
        {book.name}
      </Typography>
      
      {/* Book Details Card */}
      <Card variant="outlined" sx={{ mb: 4 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Book Overview
          </Typography>
          
          <Grid container spacing={3}>
            <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
              <Typography variant="subtitle2" color="text.secondary">
                Initial Capital
              </Typography>
              <Typography variant="body1" gutterBottom fontWeight="medium">
                ${book.initialCapital.toLocaleString()}
              </Typography>
              
              <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 2 }}>
                Regions
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                {book.regions.map((region) => (
                  <Chip key={region} label={region.toUpperCase()} size="small" />
                ))}
              </Box>
              
              <Typography variant="subtitle2" color="text.secondary">
                Markets & Instruments
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                {book.markets.map((market) => (
                  <Chip key={market} label={market} size="small" color="primary" variant="outlined" />
                ))}
                {book.instruments.map((instrument) => (
                  <Chip key={instrument} label={instrument} size="small" color="secondary" variant="outlined" />
                ))}
              </Box>
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, md: 6} as any}>
              <Typography variant="subtitle2" color="text.secondary">
                Investment Approach
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                {book.investmentApproaches.map((approach) => (
                  <Chip key={approach} label={approach} size="small" color="info" />
                ))}
              </Box>
              
              <Typography variant="subtitle2" color="text.secondary">
                Investment Timeframe
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                {book.investmentTimeframes.map((timeframe) => (
                  <Chip key={timeframe} label={timeframe} size="small" color="info" variant="outlined" />
                ))}
              </Box>
              
              <Typography variant="subtitle2" color="text.secondary">
                Position Type
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                {book.positionTypes.long && <Chip label="Long" size="small" color="success" />}
                {book.positionTypes.short && <Chip label="Short" size="small" color="error" />}
              </Box>
              
              {book.sectors && book.sectors.length > 0 && (
                <>
                  <Typography variant="subtitle2" color="text.secondary">
                    Sectors
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {book.sectors.map((sector) => (
                      <Chip key={sector} label={sector} size="small" />
                    ))}
                  </Box>
                </>
              )}
            </Grid>
          </Grid>
        </CardContent>
      </Card>
      
      {/* Simulator Card - Prominently placed in the center */}
      <Paper 
        elevation={3} 
        sx={{ 
          p: 4, 
          mb: 4, 
          textAlign: 'center',
          background: 'linear-gradient(to right, #f5f7fa, #e4e8ef)'
        }}
      >
        <Typography variant="h5" gutterBottom>
          Start Trading Simulation
        </Typography>
        
        <Typography variant="body1" sx={{ mb: 3, maxWidth: 600, mx: 'auto' }}>
          Launch the simulator to begin trading with this book's settings. 
          The simulator provides a real-time trading environment to test your strategies.
        </Typography>
        
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
      </Paper>
      
      {/* Order Management Section - Always accessible */}
      <Card variant="outlined" sx={{ mb: 4 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Conviction Management
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            You can submit and manage convictions without starting the simulator.
          </Typography>
          
          <Divider sx={{ my: 2 }} />
          
          <OrderSubmissionContainer />
        </CardContent>
      </Card>
    </Box>
  );
};

export default BookDetailsPage;