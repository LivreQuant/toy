// src/pages/HomePage.tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Grid, useMediaQuery, useTheme } from '@mui/material';
import { useAuth } from '../hooks/useAuth';
import { useBookManager } from '../hooks/useBookManager';
import { useFundManager } from '../hooks/useFundManager';
import { Book, FundProfile } from '@trading-app/types-core';

import { config, isMainApp, shouldLog } from '@trading-app/config';

// Dashboard Components
import DashboardHeader from '../components/Layout/DashboardHeader';
import FundProfileCard from '../components/Dashboard/FundProfileCard';
import TradingBooksGrid from '../components/Dashboard/TradingBooksGrid';

const HomePage: React.FC = () => {
  console.log('🏠 HomePage component rendering...');
  
  const { logout, isAuthenticated } = useAuth();
  console.log('🏠 HomePage auth state:', { isAuthenticated });
  
  const bookManager = useBookManager();
  const fundManager = useFundManager();
  const navigate = useNavigate();
  const theme = useTheme();

  const [books, setBooks] = useState<Book[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fundProfile, setFundProfile] = useState<FundProfile | null>(null);
  const [isFundLoading, setIsFundLoading] = useState(true);

  console.log('🏠 HomePage state:', {
    isAuthenticated,
    isFundLoading,
    hasFundProfile: !!fundProfile,
    booksCount: books.length,
    fundManager: !!fundManager
  });

  // Fetch fund profile first
  useEffect(() => {
    console.log('🔍 Fund profile useEffect triggered!', { isAuthenticated });
    
    const fetchFundProfile = async () => {
      console.log('🔍 Starting fetchFundProfile...');
      
      if (!isAuthenticated) {
        console.log('❌ Not authenticated, skipping fund profile fetch');
        setIsFundLoading(false);
        return;
      }
      
      if (!fundManager) {
        console.log('❌ No fundManager available');
        setIsFundLoading(false);
        return;
      }
      
      try {
        setIsFundLoading(true);
        console.log('📡 Calling fundManager.getFundProfile()...');
        
        // Add a timeout to see if the call is hanging
        const timeoutPromise = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('API call timeout after 10 seconds')), 10000)
        );
        
        const apiPromise = fundManager.getFundProfile();
        
        const response = await Promise.race([apiPromise, timeoutPromise]) as any;
        console.log('📡 Fund profile response:', response);
        
        if (response.success && response.fund) {
          console.log('✅ Fund profile loaded successfully:', response.fund);
          setFundProfile(response.fund);
        } else {
          console.log('ℹ️ No fund profile found or error:', response.error);
          setFundProfile(null);
        }
      } catch (error) {
        console.error('❌ Error fetching fund profile:', error);
        setFundProfile(null);
      } finally {
        console.log('🏁 Fund profile fetch completed');
        setIsFundLoading(false);
      }
    };
  
    fetchFundProfile();
  }, [isAuthenticated, fundManager]);

  // Only fetch books if we have a fund profile
  useEffect(() => {
    console.log('🔍 Books useEffect triggered!', { 
      hasFundProfile: !!fundProfile, 
      isAuthenticated 
    });
    
    if (!fundProfile || !isAuthenticated) {
      console.log('⏭️ Skipping books fetch - no fund profile or not authenticated');
      return;
    }
    
    const fetchBooks = async () => {
      console.log('🔍 Starting fetchBooks...');
      
      try {
        setIsLoading(true);
        const response = await bookManager.fetchBooks();
        console.log('📡 Books response:', response);
        
        if (response.success && response.books) {
          console.log('✅ Books loaded successfully:', response.books);
          setBooks(response.books);
        } else {
          console.error('❌ Failed to fetch books:', response.error);
          setBooks([]);
        }
      } catch (error) {
        console.error('❌ Error fetching books:', error);
        setBooks([]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchBooks();
  }, [fundProfile, isAuthenticated, bookManager]);

  const handleCreateBook = () => {
    navigate('/books/new');
  };

  const handleOpenBook = (bookId: string) => {
    const bookAppUrl = config.book.baseUrl;
    window.location.href = `${bookAppUrl}/books/${bookId}`;
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  console.log('🏠 HomePage about to render UI, isFundLoading:', isFundLoading);

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
                isConnected={true}
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