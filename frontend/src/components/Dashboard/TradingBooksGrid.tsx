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
import AssessmentIcon from '@mui/icons-material/Assessment';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';

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
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={onCreateBook}
              disabled={!isConnected}
            >
              Create First Book
            </Button>
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
                        label={book.status || 'Unknown'} 
                        size="small"
                        color={getStatusColor(book.status)}
                      />
                    }
                    sx={{ pb: 1 }}
                  />
                  
                  <Divider />
                  
                  <CardContent sx={{ py: 2 }}>
                    <Box sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
                      <Box 
                        sx={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'center',
                          backgroundColor: theme.palette.primary.main,
                          color: '#fff',
                          borderRadius: '50%',
                          width: 32,
                          height: 32,
                          mr: 1.5
                        }}
                      >
                        <AssessmentIcon fontSize="small" />
                      </Box>
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Capital
                        </Typography>
                        <Typography variant="subtitle1">
                          ${(book.initialCapital || 0).toLocaleString()}
                        </Typography>
                      </Box>
                    </Box>
                    
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                      <strong>Risk Level:</strong> {book.riskLevel || 'Unknown'}
                    </Typography>
                    
                    {book.marketFocus && (
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                        <strong>Focus:</strong> {book.marketFocus}
                      </Typography>
                    )}
                    
                    {book.tradingStrategy && (
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                        <strong>Strategy:</strong> {book.tradingStrategy}
                      </Typography>
                    )}
                  </CardContent>
                  
                  <Divider />
                  
                  <CardActions sx={{ justifyContent: 'space-between', p: 1 }}>
                    <Button 
                      size="small"
                      startIcon={<TrendingUpIcon />}
                      onClick={() => onOpenBook(book.id)}
                    >
                      Performance
                    </Button>
                    <Button 
                      variant="outlined"
                      size="small"
                      color="primary"
                      startIcon={<LaunchIcon />}
                      onClick={() => onOpenBook(book.id)}
                    >
                      Open Book
                    </Button>
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