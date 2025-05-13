// src/components/Dashboard/QuickActions.tsx
import React from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Divider,
  Typography,
  useTheme
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import FileUploadIcon from '@mui/icons-material/FileUpload';
import SettingsIcon from '@mui/icons-material/Settings';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import SpeedIcon from '@mui/icons-material/Speed';

interface QuickActionsProps {
  onCreateBook: () => void;
  onEditProfile: () => void;
  hasBooks: boolean;
  isConnected: boolean;
}

const QuickActions: React.FC<QuickActionsProps> = ({
  onCreateBook,
  onEditProfile,
  hasBooks,
  isConnected
}) => {
  const theme = useTheme();

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
            <SpeedIcon sx={{ mr: 1 }} />
            <Typography variant="h6">Quick Actions</Typography>
          </Box>
        }
        sx={{ 
          backgroundColor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.01)',
          borderBottom: `1px solid ${theme.palette.divider}`
        }}
      />
      
      <CardContent sx={{ p: 2 }}>
        <Button
          fullWidth
          variant="contained"
          startIcon={<AddIcon />}
          onClick={onCreateBook}
          disabled={!isConnected}
          sx={{ mb: 2 }}
        >
          Create New Book
        </Button>
        
        <Button
          fullWidth
          variant="outlined"
          startIcon={<EditIcon />}
          onClick={onEditProfile}
          sx={{ mb: 2 }}
        >
          Edit Fund Profile
        </Button>
        
        <Button
          fullWidth
          variant="outlined"
          color="success"
          startIcon={<PlayArrowIcon />}
          disabled={!hasBooks || !isConnected}
          sx={{ mb: 2 }}
        >
          Start Simulation
        </Button>
        
        <Button
          fullWidth
          variant="outlined"
          startIcon={<FileUploadIcon />}
          disabled={!hasBooks || !isConnected}
          sx={{ mb: 2 }}
        >
          Upload Orders
        </Button>
        
        <Divider sx={{ my: 2 }} />
        
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            sx={{ flex: 1 }}
            variant="text"
            startIcon={<SettingsIcon />}
            size="small"
          >
            Settings
          </Button>
          
          <Button
            sx={{ flex: 1 }}
            variant="text"
            startIcon={<HelpOutlineIcon />}
            size="small"
          >
            Help
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};

export default QuickActions;