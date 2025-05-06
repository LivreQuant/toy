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
    const fetchBooks = async () => {
      try {
        setIsLoading(true);
        await bookManager.fetchBooks();
        
        // Safely convert and type the books
        const storedBooksObj = (window as any).bookState?.getState()?.books || {};
        const storedBooks = Object.values(storedBooksObj).filter((book: any): book is Book => {
          // Validate that the book matches the Book type
          return (
            book &&
            typeof book === 'object' &&
            typeof book.id === 'string' &&
            typeof book.name === 'string' &&
            typeof book.initialCapital === 'number' &&
            ['low', 'medium', 'high'].includes(book.riskLevel) &&
            ['CONFIGURED', 'ACTIVE', 'ARCHIVED'].includes(book.status)
          );
        });

        setBooks(storedBooks);
      } catch (error) {
        addToast('error', 'Failed to fetch books');
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
          <div className="books-list">
            {books.map(book => (
              <div key={book.id} className="book-card">
                <div className="book-info">
                  <h3>{book.name}</h3>
                  <div className="book-details">
                    <span className="detail">Risk: {book.riskLevel}</span>
                    <span className="detail">Capital: ${book.initialCapital.toLocaleString()}</span>
                    {book.marketFocus && <span className="detail">Focus: {book.marketFocus}</span>}
                  </div>
                  <div className="book-status">
                    Status: <span className={`status-${book.status.toLowerCase()}`}>
                      {book.status}
                    </span>
                  </div>
                </div>
                <div className="book-actions">
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