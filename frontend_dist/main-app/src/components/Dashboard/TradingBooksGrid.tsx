// src/components/Dashboard/TradingBooksGrid.tsx
import React from 'react';
import {
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  Typography,
  useTheme
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import LaunchIcon from '@mui/icons-material/Launch';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import EditIcon from '@mui/icons-material/Edit';
import { useNavigate } from 'react-router-dom';

interface TradingBooksGridProps {
  books: any[];
  isLoading: boolean;
  isConnected: boolean;
  onCreateBook: () => void;
  onOpenBook: (bookId: string) => void;
}

const TradingBooksGrid: React.FC<TradingBooksGridProps> = ({
  books,
  isLoading,
  isConnected,
  onCreateBook,
  onOpenBook
}) => {
  const theme = useTheme();
  const navigate = useNavigate();

  // Helper function to format date
  const formatDate = (timestamp: number): string => {
    if (!timestamp) return 'Unknown date';
    const date = new Date(timestamp * 1000); // Convert seconds to milliseconds if needed
    return date.toLocaleDateString();
  };

  // Helper function to calculate and format time elapsed
  const getTimeElapsed = (timestamp: number): string => {
    if (!timestamp) return 'Unknown date';
    const now = Date.now();
    const millisecondsDiff = now - timestamp * 1000; // Convert seconds to milliseconds if needed
    const daysDiff = Math.floor(millisecondsDiff / (1000 * 60 * 60 * 24));
    
    if (daysDiff < 1) {
      return 'Today';
    } else if (daysDiff === 1) {
      return 'Yesterday';
    } else if (daysDiff < 30) {
      return `${daysDiff} days ago`;
    } else if (daysDiff < 365) {
      const months = Math.floor(daysDiff / 30);
      return `${months} ${months === 1 ? 'month' : 'months'} ago`;
    } else {
      const years = Math.floor(daysDiff / 365);
      return `${years} ${years === 1 ? 'year' : 'years'} ago`;
    }
  };

  // Status color mapping
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ACTIVE':
        return 'success';
      case 'CONFIGURED':
        return 'primary';
      case 'ARCHIVED':
        return 'default';
      default:
        return 'default';
    }
  };

  return (
    <Card 
      elevation={0} 
      sx={{ 
        mb: 3,
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 2
      }}
    >
      <CardHeader
        title={
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <AccountBalanceWalletIcon sx={{ mr: 1 }} />
            <Typography variant="h6">Trading Books</Typography>
          </Box>
        }
        action={
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={onCreateBook}
            disabled={!isConnected}
          >
            Create Book
          </Button>
        }
        sx={{ 
          backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.01)',
          borderBottom: `1px solid ${theme.palette.divider}`
        }}
      />
      
      <CardContent sx={{ p: 3 }}>
        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : books.length === 0 ? (
          <Box sx={{ 
            textAlign: 'center', 
            p: 4, 
            backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.01)',
            borderRadius: 1
          }}>
            <FolderOpenIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" gutterBottom>No Trading Books</Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Create your first trading book to start managing your investments.
            </Typography>
          </Box>
        ) : (
          <Grid container spacing={3}>
            {books.map((book) => (
              <Grid {...{component: "div", item: true, xs: 12, sm: 6, lg: 4, key: book.id} as any}>
                <Card 
                  variant="outlined" 
                  sx={{ 
                    height: '100%',
                    transition: 'all 0.2s ease-in-out',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: theme.shadows[3]
                    }
                  }}
                >
                  <CardHeader
                    title={book.name || 'Unnamed Book'}
                    titleTypographyProps={{ variant: 'subtitle1', fontWeight: 'medium' }}
                    action={
                      <Chip 
                        label={`Created ${getTimeElapsed(book.createdAt)}`}
                        size="small"
                        color={getStatusColor(book.status || 'CONFIGURED')}
                      />
                    }
                    sx={{ pb: 1 }}
                  />
                  
                  <Divider />
                  
                  <CardContent sx={{ py: 2 }}>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Typography variant="body2" color="text.secondary">
                        <strong>Regions:</strong> {book.regions?.join(', ') || 'N/A'}
                      </Typography>

                      <Typography variant="body2" color="text.secondary">
                        <strong>Markets:</strong> {book.markets?.join(', ') || 'N/A'}
                      </Typography>

                      <Typography variant="body2" color="text.secondary">
                        <strong>Instruments:</strong> {book.instruments?.join(', ') || 'N/A'}
                      </Typography>

                      <Typography variant="body2" color="text.secondary">
                        <strong>Approach:</strong> {book.investmentApproaches?.join(', ') || 'N/A'}
                      </Typography>
                    </Box>
                  </CardContent>
                  
                  <Divider />
                  
                  <CardActions sx={{ justifyContent: 'space-between', p: 1 }}>
                    <Box>
                      <Button 
                        variant="outlined"
                        size="small"
                        color="primary"
                        startIcon={<TrendingUpIcon />}
                        onClick={() => onOpenBook(book.bookId)}
                        sx={{ mr: 1 }}
                        disabled
                      >
                        Performance
                      </Button>
                      <Button 
                        variant="outlined"
                        size="small"
                        color="primary"
                        startIcon={<EditIcon />}
                        onClick={() => navigate(`/books/${book.bookId}/edit`)}
                        sx={{ mr: 1 }}
                      >
                        Edit
                      </Button>
                      <Button 
                        variant="outlined"
                        size="small"
                        color="primary"
                        startIcon={<LaunchIcon />}
                        onClick={() => onOpenBook(book.bookId)}
                      >
                        Open
                      </Button>
                    </Box>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </CardContent>
    </Card>
  );
};

export default TradingBooksGrid;