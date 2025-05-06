import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useConnection } from '../hooks/useConnection';
import { useBookManager } from '../hooks/useBookManager';
import { Book } from '../types';
import ConnectionStatusIndicator from '../components/Common/ConnectionStatusIndicator';
import './HomePage.css';

// Instead of relying solely on the local state, let's also directly access the global state
import { bookState } from '../state/book-state';

const HomePage: React.FC = () => {
  useRequireAuth();
  const { logout } = useAuth();
  const { connectionManager, connectionState, isConnected } = useConnection();
  const { addToast } = useToast();
  const bookManager = useBookManager();
  const navigate = useNavigate();

  const [books, setBooks] = useState<Book[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Subscribe to book state changes
    const subscription = bookState.getState$().subscribe(state => {
      console.log('Book state updated:', state);
      const bookArray = Object.values(state.books);
      console.log('Book array from state:', bookArray);
      setBooks(bookArray);
    });
    
    return () => {
      subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    const fetchBooks = async () => {
      try {
        setIsLoading(true);
        const response = await bookManager.fetchBooks();
        
        console.log('Book API response:', response);
        
        if (response.success && response.books) {
          console.log('Books from API:', response.books);
          setBooks(response.books);
        } else {
          console.log('No books returned or error:', response);
          setBooks([]);
        }
      } catch (error) {
        console.error('Error fetching books:', error);
        addToast('error', 'Failed to fetch books');
        setBooks([]);
      } finally {
        setIsLoading(false);
      }
    };
  
    if (isConnected) {
      fetchBooks();
    }
  }, [isConnected, bookManager, addToast]);

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      addToast('error', `Logout failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  const handleCreateBook = () => {
    navigate('/books/new');
  };

  const handleOpenBook = (bookId: string) => {
    navigate(`/books/${bookId}`);
  };

  const handleManualReconnect = () => {
    if (connectionManager) {
      connectionManager.manualReconnect();
      addToast('info', 'Attempting to reconnect...');
    }
  };

  console.log('Books array in component:', books);
  console.log('Books length:', books.length);
  console.log('isLoading:', isLoading);

  return (
    <div className="home-page">
      <header className="home-header">
        <h1>Trading Platform</h1>
        <button onClick={handleLogout} className="logout-button">
          Logout
        </button>
      </header>

      <div className="status-panel">
        <h2>Connection</h2>
        {connectionState ? (
          <ConnectionStatusIndicator
            state={connectionState}
            onManualReconnect={handleManualReconnect}
          />
        ) : (
          <p>Loading connection state...</p>
        )}
      </div>

      <div className="books-panel">
        <div className="panel-header">
          <h2>Your Trading Books</h2>
          <button 
            onClick={handleCreateBook}
            className="create-button"
            disabled={!isConnected}
          >
            Create New Book
          </button>
        </div>
        
        {isLoading ? (
          <div className="loading-placeholder">Loading your books...</div>
        ) : books.length === 0 ? (
          <div className="empty-list">
            <p>You don't have any trading books yet.</p>
            <button 
              onClick={handleCreateBook}
              className="create-button-large"
              disabled={!isConnected}
            >
              Create Your First Book
            </button>
          </div>
        ) : (
          <div className="simulation-list">
            {books.map(book => (
              <div key={book.id} className="simulation-card">
                <div className="simulation-info">
                  <h3>{book.name || 'Unnamed Book'}</h3>
                  <div className="simulation-details">
                    <span className="detail">Risk: {book.riskLevel || 'Unknown'}</span>
                    <span className="detail">Capital: ${(book.initialCapital || 0).toLocaleString()}</span>
                    {book.marketFocus && <span className="detail">Focus: {book.marketFocus}</span>}
                  </div>
                  <div className="simulation-status">
                    Status: <span className={`status-${(book.status || 'unknown').toLowerCase()}`}>
                      {book.status || 'Unknown'}
                    </span>
                  </div>
                </div>
                <div className="simulation-actions">
                  <button 
                    onClick={() => handleOpenBook(book.id)}
                    className="action-button open-button"
                    disabled={!isConnected}
                  >
                    Open Book
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default HomePage;