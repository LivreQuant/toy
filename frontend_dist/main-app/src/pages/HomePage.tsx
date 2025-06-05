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

const HomePage: React.FC = () => {
  const { logout } = useAuth();
  const { isConnected } = useConnection();
  const bookManager = useBookManager();
  const fundManager = useFundManager();
  const navigate = useNavigate();
  const theme = useTheme();

  const [books, setBooks] = useState<Book[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fundProfile, setFundProfile] = useState<FundProfile | null>(null);
  const [isFundLoading, setIsFundLoading] = useState(true);

  // Fetch fund profile first
  useEffect(() => {
    const fetchFundProfile = async () => {
      if (!isConnected) return;
      
      try {
        setIsFundLoading(true);
        const response = await fundManager.getFundProfile();
        
        if (response.success && response.fund) {
          setFundProfile(response.fund);
        } else {
          setFundProfile(null);
        }
      } catch (error) {
        console.error('Error fetching fund profile:', error);
        setFundProfile(null);
      } finally {
        setIsFundLoading(false);
      }
    };
  
    if (isConnected) {
      fetchFundProfile();
    }
  }, [isConnected, fundManager]);

  // Only fetch books if we have a fund profile
  useEffect(() => {
    if (!isConnected || !fundProfile) {
      return;
    }
    
    const fetchBooks = async () => {
      try {
        setIsLoading(true);
        const response = await bookManager.fetchBooks();
        
        if (response.success && response.books) {
          setBooks(response.books);
        } else {
          console.error('Failed to fetch books:', response.error);
          setBooks([]);
        }
      } catch (error) {
        console.error('Error fetching books:', error);
        setBooks([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchBooks();
  }, [isConnected, fundProfile, bookManager]);

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
        <Grid container spacing={3}>
          <Grid {...{component: "div", item: true, xs: 12, lg: 12, sx: { width: '100%' }} as any}>
            <FundProfileCard 
              onEditProfile={() => navigate(fundProfile ? '/profile/edit' : '/profile/create')}
              fundProfile={fundProfile}
              isLoading={isFundLoading}
            />
            
            {fundProfile && (
              <TradingBooksGrid 
                books={books} 
                isLoading={isLoading}
                isConnected={isConnected}
                onCreateBook={handleCreateBook}
                onOpenBook={handleOpenBook}
              />
            )}
          </Grid>
        </Grid>
      </Box>
    </Box>
  );
};

export default HomePage;