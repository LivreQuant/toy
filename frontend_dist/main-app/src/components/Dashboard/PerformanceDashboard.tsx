// src/components/Dashboard/PerformanceDashboard.tsx
import React from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Divider,
  Grid,
  LinearProgress,
  Typography,
  Tooltip,
  useTheme
} from '@mui/material';
import LeaderboardIcon from '@mui/icons-material/Leaderboard';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import TimelineIcon from '@mui/icons-material/Timeline';

interface PerformanceDashboardProps {
  books: any[];
}

// Placeholder component for a chart
const PlaceholderChart: React.FC<{ height?: number, title: string }> = ({ height = 200, title }) => {
  const theme = useTheme();
  
  return (
    <Box 
      sx={{ 
        height, 
        width: '100%', 
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.01)',
        borderRadius: 1
      }}
    >
      <ShowChartIcon sx={{ fontSize: 40, color: 'text.secondary', mb: 1 }} />
      <Typography variant="body2" color="text.secondary">
        {title}
      </Typography>
    </Box>
  );
};

const PerformanceDashboard: React.FC<PerformanceDashboardProps> = ({ books }) => {
  const theme = useTheme();
  const totalCapital = books.reduce((total, book) => total + (book.initialCapital || 0), 0);
  
  // This would normally come from actual performance data
  const mockPerformanceData = {
    monthlyReturn: 4.2,
    yearToDateReturn: 12.7,
    volatility: 8.3,
    sharpeRatio: 1.8,
    rank: 12,
    percentile: 75
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
            <Typography variant="h6">Performance Dashboard</Typography>
          </Box>
        }
        // src/components/Dashboard/PerformanceDashboard.tsx (continued)
        action={
            <Tooltip title="Coming soon">
              <span>
                <Button 
                  variant="outlined"
                  startIcon={<LeaderboardIcon />}
                  disabled
                >
                  Compare to Peers
                </Button>
              </span>
            </Tooltip>
          }
          sx={{ 
            backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.01)',
            borderBottom: `1px solid ${theme.palette.divider}`
          }}
        />
        
        <CardContent sx={{ p: 3 }}>
          <Grid container spacing={3}>
            {/* Key Metrics Cards */}
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, md: 3} as any}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardContent>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Total Capital
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 'medium', mb: 1 }}>
                    ${totalCapital.toLocaleString()}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                    {books.length} active trading book{books.length !== 1 ? 's' : ''}
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={70} 
                    sx={{ mt: 1, height: 6, borderRadius: 3 }}
                  />
                </CardContent>
              </Card>
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, md: 3} as any}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardContent>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Monthly Return
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <Typography variant="h4" sx={{ fontWeight: 'medium' }}>
                      {mockPerformanceData.monthlyReturn}%
                    </Typography>
                    <TrendingUpIcon 
                      sx={{ 
                        ml: 1, 
                        color: 'success.main',
                        fontSize: 20 
                      }} 
                    />
                  </Box>
                  <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                    vs. benchmark +2.1%
                  </Typography>
                  <Box sx={{ 
                    mt: 1,
                    pt: 1,
                    borderTop: `1px dashed ${theme.palette.divider}`,
                    display: 'flex',
                    justifyContent: 'space-between'
                  }}>
                    <Typography variant="caption" color="text.secondary">
                      YTD Return
                    </Typography>
                    <Typography variant="caption" fontWeight="medium" color="success.main">
                      +{mockPerformanceData.yearToDateReturn}%
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, md: 3} as any}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardContent>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Volatility
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 'medium', mb: 1 }}>
                    {mockPerformanceData.volatility}%
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <Box sx={{ flexGrow: 1, mr: 1 }}>
                      <LinearProgress 
                        variant="determinate" 
                        value={mockPerformanceData.volatility / 20 * 100} 
                        color="warning"
                        sx={{ height: 6, borderRadius: 3 }}
                      />
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      Medium
                    </Typography>
                  </Box>
                  <Box sx={{ 
                    mt: 1,
                    pt: 1,
                    borderTop: `1px dashed ${theme.palette.divider}`,
                    display: 'flex',
                    justifyContent: 'space-between'
                  }}>
                    <Typography variant="caption" color="text.secondary">
                      Sharpe Ratio
                    </Typography>
                    <Typography variant="caption" fontWeight="medium">
                      {mockPerformanceData.sharpeRatio}
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, sm: 6, md: 3} as any}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardContent>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                    Peer Ranking
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 'medium', mb: 1 }}>
                    #{mockPerformanceData.rank}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                    Top {100 - mockPerformanceData.percentile}% of traders
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={mockPerformanceData.percentile} 
                    color="success"
                    sx={{ mt: 1, height: 6, borderRadius: 3 }}
                  />
                </CardContent>
              </Card>
            </Grid>
            
            {/* Charts */}
            <Grid {...{component: "div", item: true, xs: 12, md: 8} as any}>
              <Card variant="outlined">
                <CardHeader 
                  title="Performance History"
                  titleTypographyProps={{ variant: 'subtitle1' }}
                  action={
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Button size="small" variant="outlined">1M</Button>
                      <Button size="small" variant="contained">3M</Button>
                      <Button size="small" variant="outlined">YTD</Button>
                      <Button size="small" variant="outlined">1Y</Button>
                    </Box>
                  }
                />
                <Divider />
                <CardContent>
                  <PlaceholderChart height={250} title="Performance Chart Coming Soon" />
                </CardContent>
              </Card>
            </Grid>
            
            <Grid {...{component: "div", item: true, xs: 12, md: 4} as any}>
              <Card variant="outlined" sx={{ height: '100%' }}>
                <CardHeader 
                  title="Asset Allocation"
                  titleTypographyProps={{ variant: 'subtitle1' }}
                />
                <Divider />
                <CardContent>
                  <PlaceholderChart height={250} title="Asset Allocation Chart Coming Soon" />
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    );
  };
  
  export default PerformanceDashboard;