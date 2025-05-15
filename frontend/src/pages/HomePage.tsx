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
  const fundManager = useFundManager(); // Add this hook
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const [books, setBooks] = useState<Book[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [fundProfile, setFundProfile] = useState<FundProfile | null>(null); // Add this state
  const [isFundLoading, setIsFundLoading] = useState(true); // Add this state


  // Fetch fund profile
  useEffect(() => {
    const fetchFundProfile = async () => {
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
          {/* Main column - Fund Profile & Books */}
          <Grid {...{component: "div", item: true, xs: 12, lg: 8} as any}>
            <FundProfileCard 
              onEditProfile={() => navigate('/profile/edit')}
              fundProfile={fundProfile}
              isLoading={isFundLoading}
            />
            
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