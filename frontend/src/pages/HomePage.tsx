// In HomePage.tsx, add the fundProfile state

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useToast } from '../hooks/useToast';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useConnection } from '../hooks/useConnection';
import { useBookManager } from '../hooks/useBookManager';
import { Book } from '../types';
import './HomePage.css';

// Instead of relying solely on the local state, let's also directly access the global state
import { bookState } from '../state/book-state';

// Define FundProfile interface
interface TeamMember {
  id: string;
  name: string;
  role: string;
  yearsExperience: string;
  education: string;
  previousEmployment: string;
  birthDate: string;
  linkedin?: string;
}

interface FundProfile {
  fundName: string;
  legalStructure: string;
  location: string;
  yearEstablished: string;
  aumRange: string;
  investmentStrategy: string;
  teamMembers: TeamMember[];
  complianceOfficer: string;
  complianceEmail: string;
  fundAdministrator: string;
  primeBroker: string;
  auditor: string;
  legalCounsel: string;
  regulatoryRegistrations: string;
  previousPerformance: string;
  references: string;
}

const HomePage: React.FC = () => {
  useRequireAuth();
  const { logout } = useAuth();
  const { isConnected } = useConnection();
  const { addToast } = useToast();
  const bookManager = useBookManager();
  const navigate = useNavigate();

  const [books, setBooks] = useState<Book[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  // Add fundProfile state
  const [fundProfile, setFundProfile] = useState<FundProfile | null>(null);

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

  // Add effect to fetch fund profile
  useEffect(() => {
    // TODO: Implement actual API call to fetch fund profile
    // For now, just simulate it with localStorage
    const fetchFundProfile = () => {
      try {
        const savedProfile = localStorage.getItem('fundProfile');
        if (savedProfile) {
          setFundProfile(JSON.parse(savedProfile));
        }
      } catch (error) {
        console.error('Error fetching fund profile:', error);
      }
    };

    if (isConnected) {
      fetchFundProfile();
    }
  }, [isConnected]);

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

  console.log('Books array in component:', books);
  console.log('Books length:', books.length);
  console.log('isLoading:', isLoading);

  return (
    <div className="home-page">
      <header className="home-header">
        <h1>DigitalTrader</h1>
        <button onClick={handleLogout} className="logout-button">
          Logout
        </button>
      </header>

      {/* USER - FUND PROFILE */}
      <div className="fund-profile-panel">
        <div className="panel-header">
          <h2>Fund Profile</h2>
          <button 
            onClick={() => navigate('/profile/create')}
            className="create-button"
            disabled={!isConnected}
          >
            {fundProfile ? 'Edit Fund Profile' : 'Create Fund Profile'}
          </button>
        </div>
        
        {fundProfile ? (
          <div className="fund-profile-summary">
            <div className="fund-info">
              <h3>{fundProfile.fundName}</h3>
              <div className="fund-details">
                <span className="detail">Structure: {fundProfile.legalStructure}</span>
                <span className="detail">Location: {fundProfile.location}</span>
                <span className="detail">Est: {fundProfile.yearEstablished}</span>
                {fundProfile.aumRange && <span className="detail">AUM: {fundProfile.aumRange}</span>}
              </div>
              <p className="fund-strategy">{fundProfile.investmentStrategy}</p>
            </div>
            <div className="team-summary">
              <h4>Team: {fundProfile.teamMembers.length} member(s)</h4>
              <div className="team-members">
                {fundProfile.teamMembers.slice(0, 3).map(member => (
                  <div key={member.id} className="team-member-pill">
                    {member.name} ({member.role})
                  </div>
                ))}
                {fundProfile.teamMembers.length > 3 && 
                  <div className="team-member-pill more">+{fundProfile.teamMembers.length - 3} more</div>
                }
              </div>
            </div>
          </div>
        ) : (
          <div className="empty-fund-profile">
            <p>No fund profile has been created yet. Create a profile to share your fund's information with investors.</p>
            <button 
              onClick={() => navigate('/profile/create')}
              className="create-button-large"
              disabled={!isConnected}
            >
              Create Fund Profile
            </button>
          </div>
        )}
      </div>

      {/* PORTFOLIOS */}
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
                  <div className="simulation-parameters">
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
                    View Performance
                  </button>
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