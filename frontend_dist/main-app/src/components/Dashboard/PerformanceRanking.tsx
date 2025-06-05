// src/components/Dashboard/PerformanceRanking.tsx
import React from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Divider,
  LinearProgress,
  Tooltip,
  Typography,
  useTheme
} from '@mui/material';
import LeaderboardIcon from '@mui/icons-material/Leaderboard';
import EmojiEventsIcon from '@mui/icons-material/EmojiEvents';

const PerformanceRanking: React.FC = () => {
  const theme = useTheme();
  
  // Mock ranking data
  const rankingData = {
    rank: 12,
    percentile: 75,
    totalTraders: 100,
    category: 'Equity Long/Short'
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
            <LeaderboardIcon sx={{ mr: 1 }} />
            <Typography variant="h6">Performance Ranking</Typography>
          </Box>
        }
        action={
          <Tooltip title="Coming soon">
            <span>
              <Button 
                variant="outlined"
                size="small"
                disabled
              >
                View Leaderboard
              </Button>
            </span>
          </Tooltip>
        }
        sx={{ 
          backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.01)',
          borderBottom: `1px solid ${theme.palette.divider}`
        }}
      />
      
      <CardContent>
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          mb: 3 
        }}>
          <Box 
            sx={{ 
              width: 50, 
              height: 50, 
              borderRadius: '50%', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              bgcolor: 'success.main',
              color: '#fff',
              fontWeight: 'bold',
              fontSize: '1.25rem',
              mr: 2
            }}
          >
            {rankingData.rank}
          </Box>
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="body2" gutterBottom>
              Your Current Rank
            </Typography>
            <Typography variant="h6" sx={{ fontWeight: 'medium' }}>
              #{rankingData.rank} of {rankingData.totalTraders} Traders
            </Typography>
          </Box>
        </Box>
        
        <Box sx={{ mb: 4 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Performance Percentile
            </Typography>
            <Typography variant="body2" fontWeight="medium">
              {rankingData.percentile}%
            </Typography>
          </Box>
          <LinearProgress 
            variant="determinate" 
            value={rankingData.percentile} 
            sx={{ height: 8, borderRadius: 4 }}
            color="success"
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            You're outperforming {rankingData.percentile}% of traders in your category
          </Typography>
        </Box>
        
        <Divider sx={{ my: 2 }} />
        
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <EmojiEventsIcon color="warning" sx={{ mr: 1 }} />
          <Typography variant="body2" color="text.secondary">
            Category: {rankingData.category}
          </Typography>
        </Box>
        
        <Box 
          sx={{ 
            mt: 2,
            py: 2, 
            px: 2, 
            borderRadius: 1,
            backgroundColor: theme.palette.mode === 'dark' 
              ? 'rgba(255,255,255,0.03)' 
              : 'rgba(0,0,0,0.01)',
            border: `1px dashed ${theme.palette.divider}`
          }}
        >
          <Typography variant="body2" align="center">
            Performance analytics update weekly. Next update in 3 days.
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default PerformanceRanking;