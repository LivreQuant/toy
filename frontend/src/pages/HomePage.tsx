// src/pages/HomePage.tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Grid, useMediaQuery, useTheme } from '@mui/material';
import { useAuth } from '../hooks/useAuth';
import { useConnection } from '../hooks/useConnection';
import { useBookManager } from '../hooks/useBookManager';
import { useFundManager } from '../hooks/useFundManager';
import { Book, FundProfile } from '../types';

// Dashboard Components
import DashboardHeader from '../components/Layout/DashboardHeader';
import FundProfileCard from '../components/Dashboard/FundProfileCard';
import TradingBooksGrid from '../components/Dashboard/TradingBooksGrid';
import PerformanceDashboard from '../components/Dashboard/PerformanceDashboard';
import ActivityFeed from '../components/Dashboard/ActivityFeed';
import QuickActions from '../components/Dashboard/QuickActions';
import PerformanceRanking from '../components/Dashboard/PerformanceRanking';

const HomePage: React.FC = () => {
  const { logout } = useAuth();
  const { isConnected } = useConnection();
  const bookManager = useBookManager();
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const [books, setBooks] = useState<Book[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch books
  useEffect(() => {
    const fetchBooks = async () => {
      try {
        setIsLoading(true);
        const response = await bookManager.fetchBooks();
        
        if (response.success && response.books) {
          setBooks(response.books);
        } else {
          setBooks([]);
        }
      } catch (error) {
        console.error('Error fetching books:', error);
        setBooks([]);
      } finally {
        setIsLoading(false);
      }
    };
  
    if (isConnected) {
      fetchBooks();
    }
  }, [isConnected, bookManager]);

  const handleCreateBook = () => {
    navigate('/books/new');
  };

  const handleOpenBook = (bookId: string) => {
    navigate(`/books/${bookId}`);
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <Box sx={{ 
      backgroundColor: theme.palette.mode === 'dark' ? '#121212' : '#f0f2f5',
      minHeight: '100vh'
    }}>
      <DashboardHeader onLogout={handleLogout} />
      
      <Box sx={{ p: { xs: 2, md: 3 }, maxWidth: 1400, mx: 'auto' }}>
        <Grid {...{component: "div", spacing: 3} as any}>
          {/* Main column - Fund Profile & Books */}
          <Grid {...{component: "div", item: true, xs: 12, lg: 8} as any}>
            <FundProfileCard onEditProfile={() => navigate('/profile/create')} />
            
            <TradingBooksGrid 
              books={books} 
              isLoading={isLoading} 
              isConnected={isConnected}
              onCreateBook={handleCreateBook}
              onOpenBook={handleOpenBook}
            />
          </Grid>
          
          {/* Side column - Activity & Actions */}
          {/*
          <Grid {...{component: "div", item: true, xs: 12, lg: 4} as any}>
            <ActivityFeed books={books} />
            
            <QuickActions 
              onCreateBook={handleCreateBook}
              onEditProfile={() => navigate('/profile/create')}
              hasBooks={books.length > 0}
              isConnected={isConnected}
            />
            
            <PerformanceRanking />
          </Grid>
          */}

          {/* Full width - Performance Dashboard */}
          {/*
          <Grid {...{component: "div", item: true, xs: 12} as any}>
            <PerformanceDashboard books={books} />
          </Grid>
          */}
        </Grid>
      </Box>
    </Box>
  );
};

export default HomePage;