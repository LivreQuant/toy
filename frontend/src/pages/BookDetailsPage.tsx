import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useConnection } from '../hooks/useConnection';
import { useToast } from '../hooks/useToast';
import { useBookManager } from '../hooks/useBookManager';
import { Book } from '../types';
import CsvOrderUpload from '../components/Simulator/CsvOrderUpload';
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
            <div className="detail-item">
              <span className="label">Risk Level</span>
              <span className="value">{book.riskLevel}</span>
            </div>
            {book.marketFocus && (
              <div className="detail-item">
                <span className="label">Market Focus</span>
                <span className="value">{book.marketFocus}</span>
              </div>
            )}
            <div className="detail-item">
              <span className="label">Status</span>
              <span className={`value status-${book.status.toLowerCase()}`}>
                {book.status}
              </span>
            </div>
            {book.tradingStrategy && (
              <div className="detail-item">
                <span className="label">Trading Strategy</span>
                <span className="value">{book.tradingStrategy}</span>
              </div>
            )}
            {book.maxPositionSize !== undefined && (
              <div className="detail-item">
                <span className="label">Max Position Size</span>
                <span className="value">${book.maxPositionSize.toLocaleString()}</span>
              </div>
            )}
            {book.maxTotalRisk !== undefined && (
              <div className="detail-item">
                <span className="label">Max Total Risk</span>
                <span className="value">${book.maxTotalRisk.toLocaleString()}</span>
              </div>
            )}
          </div>
        </div>
        
        {/* Start Simulator Button */}
        <div className="action-section">
          <button 
            onClick={handleStartSimulator}
            className="start-simulator-button"
            disabled={isStartingSimulator || !isConnected}
          >
            {isStartingSimulator ? 'Starting Simulator...' : 'Start Simulator'}
          </button>
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