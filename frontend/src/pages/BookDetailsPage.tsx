import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useConnection } from '../hooks/useConnection';
import { useToast } from '../hooks/useToast';
import { useBookManager } from '../hooks/useBookManager';
import { Book } from '../types';
import CsvOrderUpload from '../components/Simulator/CsvOrderUpload';

import { Box, Button } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';

import './BookDetailsPage.css';

// Define the API response type
interface BookApiResponse {
  id: string;
  user_id: string;
  book_id: string;
  name: string;
  parameters: string;
  activeAt: number;
  expireAt: number;
}

// Helper function to parse book parameters
const parseBookParameters = (parametersStr: string): Record<string, any> => {
  try {
    // Parse JSON string into array of parameter arrays
    const parametersArray = JSON.parse(parametersStr);
    
    // Process parameters into a usable structure
    const result: Record<string, any> = {
      regions: [],
      markets: [],
      instruments: [],
      investmentApproaches: [],
      investmentTimeframes: [],
      sectors: [],
      positionTypes: { long: false, short: false }
    };
    
    parametersArray.forEach((param: [string, string, string]) => {
      const [category, subcategory, value] = param;
      
      switch(category) {
        case 'Region':
          result.regions.push(value);
          break;
        case 'Market':
          result.markets.push(value);
          break;
        case 'Instrument':
          result.instruments.push(value);
          break;
        case 'Investment Approach':
          result.investmentApproaches.push(value);
          break;
        case 'Investment Timeframe':
          result.investmentTimeframes.push(value);
          break;
        case 'Sector':
          result.sectors.push(value);
          break;
        case 'Position':
          if (subcategory === 'Long') result.positionTypes.long = value === 'true';
          if (subcategory === 'Short') result.positionTypes.short = value === 'true';
          break;
        case 'Allocation':
          result.initialCapital = parseFloat(value);
          break;
      }
    });
    
    return result;
  } catch (e) {
    console.error('Error parsing book parameters:', e);
    return {};
  }
};

const BookDetailsPage: React.FC = () => {
  useRequireAuth();
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const { isConnected, connectionManager } = useConnection();
  const { addToast } = useToast();
  const bookManager = useBookManager();

  const [book, setBook] = useState<Book | null>(null);
  const [bookParams, setBookParams] = useState<Record<string, any>>({});
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
          // Process the raw book data - treat it as BookApiResponse
          const rawBook = response.book as unknown as BookApiResponse;
          
          // Create a book object that matches the updated Book interface
          let formattedBook: Book = {
            bookId: rawBook.book_id,
            name: rawBook.name,
            initialCapital: 0,
            regions: [],
            markets: [],
            instruments: [],
            investmentApproaches: [],
            investmentTimeframes: [],
            sectors: [],
            positionTypes: {
              long: false,
              short: false
            }
          };
          
          // Parse parameters if they exist
          if (typeof rawBook.parameters === 'string') {
            const params = parseBookParameters(rawBook.parameters);
            setBookParams(params);
            
            // Update book with parsed parameter values
            if (params.initialCapital) {
              formattedBook.initialCapital = params.initialCapital;
            }
            if (params.regions) {
              formattedBook.regions = params.regions;
            }
            if (params.markets) {
              formattedBook.markets = params.markets;
            }
            if (params.instruments) {
              formattedBook.instruments = params.instruments;
            }
            if (params.investmentApproaches) {
              formattedBook.investmentApproaches = params.investmentApproaches;
            }
            if (params.investmentTimeframes) {
              formattedBook.investmentTimeframes = params.investmentTimeframes;
            }
            if (params.sectors) {
              formattedBook.sectors = params.sectors;
            }
            if (params.positionTypes) {
              formattedBook.positionTypes = params.positionTypes;
            }
          }
          
          setBook(formattedBook);
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
      // Call the startSimulator method from connectionManager
      const result = await connectionManager.startSimulator();
      
      if (result.success) {
        addToast('success', 'Simulator started successfully');
        // Navigate to the simulator page
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
    return <div className="loading-placeholder">Loading book details...</div>;
  }

  if (!book) {
    return <div className="empty-message">Book not found</div>;
  }

  return (
    <div className="book-details-page">
      <header>
        <button onClick={handleBack} className="back-button">Back</button>
        <h1>{book.name}</h1>
      </header>

      <div className="book-summary">
        <div className="detail-section">
          <h2>Book Overview</h2>
          <div className="detail-grid">
            <div className="detail-item">
              <span className="label">Initial Capital</span>
              <span className="value">${book.initialCapital.toLocaleString()}</span>
            </div>
            
            {bookParams.investmentTimeframe && (
              <div className="detail-item">
                <span className="label">Investment Timeframe</span>
                <span className="value">{bookParams.investmentTimeframe.join(', ')}</span>
              </div>
            )}
            
            {bookParams.marketFocus && (
              <div className="detail-item">
                <span className="label">Market Focus</span>
                <span className="value">{bookParams.marketFocus}</span>
              </div>
            )}

            {book.positionTypes && (
              <div className="detail-item">
                <span className="label">Position Type</span>
                <span className="value">
                  {book.positionTypes.long ? 'Long' : ''}
                  {book.positionTypes.long && book.positionTypes.short ? ' & ' : ''}
                  {book.positionTypes.short ? 'Short' : ''}
                </span>
              </div>
            )}
          </div>
        </div>
        
        {/* Start Simulator Button */}
        <div className="action-section">
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
            <Button
              variant="outlined"
              onClick={() => navigate(`/books/${bookId}/edit`)}
              startIcon={<EditIcon />}
            >
              Edit Book
            </Button>
            
            <Button 
              onClick={handleStartSimulator}
              className="start-simulator-button"
              disabled={isStartingSimulator || !isConnected}
            >
              {isStartingSimulator ? 'Starting Simulator...' : 'Start Simulator'}
            </Button>
          </Box>
          <p className="simulator-instructions">
            Start the simulator and navigate to the simulator page to begin trading with this book.
          </p>
        </div>
        
        {/* CSV Order Upload Component */}
        <div className="orders-section">
          <h2>Manage Orders</h2>
          <CsvOrderUpload />
        </div>
      </div>
    </div>
  );
};

export default BookDetailsPage;