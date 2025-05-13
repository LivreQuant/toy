// src/components/Layout/DashboardHeader.tsx
import React, { useState } from 'react';
import { 
  AppBar, 
  Box, 
  Button, 
  Toolbar, 
  Typography, 
  IconButton, 
  Menu, 
  MenuItem, 
  Badge,
  Avatar,
  Divider,
  useTheme
} from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import NotificationsIcon from '@mui/icons-material/Notifications';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import LightModeIcon from '@mui/icons-material/LightMode';
import MenuIcon from '@mui/icons-material/Menu';
import ShowChartIcon from '@mui/icons-material/ShowChart';

interface DashboardHeaderProps {
  onLogout: () => void;
}

const DashboardHeader: React.FC<DashboardHeaderProps> = ({ onLogout }) => {
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [notificationAnchorEl, setNotificationAnchorEl] = useState<null | HTMLElement>(null);

  const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleNotificationMenu = (event: React.MouseEvent<HTMLElement>) => {
    setNotificationAnchorEl(event.currentTarget);
  };

  const handleNotificationClose = () => {
    setNotificationAnchorEl(null);
  };

  return (
    <AppBar 
      position="sticky" 
      color="default" 
      elevation={0}
      sx={{ 
        borderBottom: `1px solid ${theme.palette.divider}`,
        backgroundColor: theme.palette.background.paper 
      }}
    >
      <Toolbar sx={{ justifyContent: 'space-between' }}>
        {/* Logo Section */}
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <ShowChartIcon 
            color="primary" 
            sx={{ 
              fontSize: 32, 
              mr: 1,
              color: theme.palette.primary.main
            }} 
          />
          <Typography 
            variant="h5" 
            component="h1" 
            sx={{ 
              fontWeight: 'bold',
              background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.primary.light})`,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}
          >
            DigitalTrader
          </Typography>
        </Box>

        {/* Right Actions */}
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {/* Notifications */}
          {/*
          <IconButton 
            color="inherit" 
            onClick={handleNotificationMenu}
            size="large"
          >
            <Badge badgeContent={3} color="error">
              <NotificationsIcon />
            </Badge>
          </IconButton>
          <Menu
            anchorEl={notificationAnchorEl}
            open={Boolean(notificationAnchorEl)}
            onClose={handleNotificationClose}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          >
            <MenuItem onClick={handleNotificationClose}>
              <Typography variant="body2">Market opens in 5 minutes</Typography>
            </MenuItem>
            <MenuItem onClick={handleNotificationClose}>
              <Typography variant="body2">New trade opportunity alert</Typography>
            </MenuItem>
            <MenuItem onClick={handleNotificationClose}>
              <Typography variant="body2">Performance report ready</Typography>
            </MenuItem>
            <Divider />
            <MenuItem onClick={handleNotificationClose}>
              <Typography variant="body2" color="primary">View all notifications</Typography>
            </MenuItem>
          </Menu>
          */}

          {/* User Menu */}
          <IconButton
            onClick={handleMenu}
            color="inherit"
            size="large"
            sx={{ ml: 1 }}
          >
            <Avatar sx={{ width: 32, height: 32, bgcolor: theme.palette.primary.main }}>
              <AccountCircleIcon />
            </Avatar>
          </IconButton>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleClose}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          >
            <MenuItem onClick={handleClose}>Account Settings</MenuItem>
          </Menu>

          {/* Logout Button - visible on larger screens */}
          <Button 
            variant="outlined"
            color="error"
            onClick={onLogout}
            startIcon={<LogoutIcon />}
            sx={{
              ml: 2,
              display: { xs: 'none', sm: 'flex' } 
            }}
          >
            Logout
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default DashboardHeader;