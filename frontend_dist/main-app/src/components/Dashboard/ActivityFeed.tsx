// src/components/Dashboard/ActivityFeed.tsx
import React from 'react';
import {
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Divider,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Typography,
  useTheme
} from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import NotificationsIcon from '@mui/icons-material/Notifications';
import BookIcon from '@mui/icons-material/Book';
import PersonIcon from '@mui/icons-material/Person';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PublishIcon from '@mui/icons-material/Publish';
import StopIcon from '@mui/icons-material/Stop';
import EqualizerIcon from '@mui/icons-material/Equalizer';

interface ActivityFeedProps {
  books: any[];
}

const ActivityFeed: React.FC<ActivityFeedProps> = ({ books }) => {
  const theme = useTheme();
  
  // Generate mock activity data
  const generateMockActivities = () => {
    const now = Date.now();
    const dayInMs = 86400000;
    
    // Start with the book creation activity if we have books
    const activities = books.length > 0 ? [
      {
        id: 1,
        type: 'book_created',
        message: `Book "${books[0].name}" was created`,
        timestamp: new Date(books[0].createdAt).toLocaleString(),
        icon: <BookIcon />
      }
    ] : [];
    
    // Add more mock activities
    activities.push(
      {
        id: 2,
        type: 'profile_updated',
        message: 'Fund profile was updated',
        timestamp: new Date(now - dayInMs).toLocaleString(),
        icon: <PersonIcon />
      },
      {
        id: 3,
        type: 'simulation_started',
        message: 'Trading simulation started',
        timestamp: new Date(now - 2 * dayInMs).toLocaleString(),
        icon: <PlayArrowIcon />
      },
      {
        id: 4,
        type: 'orders_uploaded',
        message: 'Uploaded 12 orders via CSV',
        timestamp: new Date(now - 3 * dayInMs).toLocaleString(),
        icon: <PublishIcon />
      },
      {
        id: 5,
        type: 'simulation_stopped',
        message: 'Trading simulation stopped',
        timestamp: new Date(now - 4 * dayInMs).toLocaleString(),
        icon: <StopIcon />
      },
      {
        id: 6,
        type: 'performance_report',
        message: 'Monthly performance report generated',
        timestamp: new Date(now - 5 * dayInMs).toLocaleString(),
        icon: <EqualizerIcon />
      }
    );
    
    return activities;
  };
  
  const activities = generateMockActivities();
  
  const getActivityIconColor = (type: string) => {
    switch (type) {
      case 'book_created':
        return theme.palette.primary.main;
      case 'profile_updated':
        return theme.palette.secondary.main;
      case 'simulation_started':
        return theme.palette.success.main;
      case 'simulation_stopped':
        return theme.palette.error.main;
      case 'orders_uploaded':
        return theme.palette.info.main;
      case 'performance_report':
        return theme.palette.warning.main;
      default:
        return theme.palette.grey[500];
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
            <NotificationsIcon sx={{ mr: 1 }} />
            <Typography variant="h6">Recent Activity</Typography>
          </Box>
        }
        action={
          <Button
            variant="text"
            endIcon={<ArrowForwardIcon />}
            size="small"
          >
            View All
          </Button>
        }
        sx={{ 
          backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.01)',
          borderBottom: `1px solid ${theme.palette.divider}`
        }}
      />
      
      <CardContent sx={{ p: 0 }}>
        <List disablePadding>
          {activities.length > 0 ? activities.map((activity) => (
            <React.Fragment key={activity.id}>
              <ListItem alignItems="flex-start" sx={{ py: 1.5, px: 2 }}>
                <ListItemAvatar>
                  <Avatar 
                    sx={{ 
                      bgcolor: 'background.paper', 
                      color: getActivityIconColor(activity.type),
                      border: `1px solid ${theme.palette.divider}`
                    }}
                  >
                    {activity.icon}
                  </Avatar>
                </ListItemAvatar>
                <ListItemText 
                  primary={
                    <Typography variant="body2" component="span" fontWeight="medium">
                      {activity.message}
                    </Typography>
                  }
                  secondary={
                    <Typography 
                      variant="caption" 
                      color="text.secondary" 
                      component="span"
                    >
                      {activity.timestamp}
                    </Typography>
                  }
                />
              </ListItem>
              <Divider component="li" />
            </React.Fragment>
          )) : (
            <ListItem>
              <ListItemText 
                primary="No recent activity" 
                secondary="Your activities will appear here" 
                sx={{ textAlign: 'center', py: 2 }}
              />
            </ListItem>
          )}
        </List>
      </CardContent>
    </Card>
  );
};

export default ActivityFeed;