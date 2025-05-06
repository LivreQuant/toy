import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useConnection } from '../hooks/useConnection';
import { Book } from '../types';
import './BookDetailsPage.css';

const BookDetailsPage: React.FC = () => {
  useRequireAuth();
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const { isConnected } = useConnection();

  const [book, setBook] = useState<Book | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Fetch book details from book state or make an API call
    const fetchBookDetails = () => {
      const storedBooks = (window as any).bookState?.getState()?.books || {};
      const selectedBook = storedBooks[bookId || ''];
      
      if (selectedBook) {
        setBook(selectedBook);
      } else {
        // Optionally, add an API call to fetch specific book details
        navigate('/home');
      }
      
      setIsLoading(false);
    };

    if (isConnected) {
      fetchBookDetails();
    }
  }, [bookId, isConnected, navigate]);

  const handleBack = () => {
    navigate('/home');
  };

  if (isLoading) {
    return <div>Loading book details...</div>;
  }

  if (!book) {
    return <div>Book not found</div>;
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
          </div>
        </div>
      </div>
    </div>
  );
};

export default BookDetailsPage;