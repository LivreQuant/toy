// src/contexts/ThemeContext.tsx
import React, { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import { createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

type ThemeMode = 'light' | 'dark';

interface ThemeContextType {
  mode: ThemeMode;
  toggleTheme: () => void;
}

// Light theme colors
const lightTheme = {
  primary: {
    main: '#2196f3',  // Professional blue
    dark: '#1976d2',
    light: '#64b5f6',
    contrastText: '#ffffff',
  },
  secondary: {
    main: '#26a69a',  // Teal for accents
    dark: '#00796b',
    light: '#4db6ac',
    contrastText: '#ffffff',
  },
  background: {
    default: '#f5f7fa',
    paper: '#ffffff',
    card: '#ffffff',
    chart: '#ffffff',
  },
  text: {
    primary: '#212121',
    secondary: '#757575',
    hint: '#9e9e9e',
  },
  success: {
    main: '#4caf50',
    dark: '#388e3c',
  },
  error: {
    main: '#f44336',
    dark: '#d32f2f',
  },
  warning: {
    main: '#ff9800',
    dark: '#f57c00',
  },
  info: {
    main: '#2196f3',
    dark: '#1976d2',
  },
  divider: 'rgba(0, 0, 0, 0.12)',
};

// Dark theme colors - optimized for financial data
const darkTheme = {
  primary: {
    main: '#2196f3',  // Keep brand blue consistent
    dark: '#1976d2',
    light: '#64b5f6',
    contrastText: '#ffffff',
  },
  secondary: {
    main: '#26a69a',  // Keep accent color
    dark: '#00796b',
    light: '#4db6ac',
    contrastText: '#ffffff',
  },
  background: {
    default: '#121212',
    paper: '#1e1e1e',
    card: '#232323',
    chart: '#1a1a1a',
  },
  text: {
    primary: '#ffffff',
    secondary: '#b3b3b3',
    hint: '#7a7a7a',
  },
  success: {
    main: '#66bb6a',  // Brighter green for dark mode
    dark: '#43a047',
  },
  error: {
    main: '#ef5350',  // Brighter red for dark mode
    dark: '#e53935',
  },
  warning: {
    main: '#ffa726',  // Brighter orange for dark mode
    dark: '#fb8c00',
  },
  info: {
    main: '#42a5f5',  // Brighter blue for dark mode
    dark: '#1e88e5',
  },
  divider: 'rgba(255, 255, 255, 0.12)',
};

// Create the actual Material-UI themes
const createLightTheme = () => createTheme({
  palette: {
    mode: 'light',
    ...lightTheme,
  },
  typography: {
    fontFamily: "'Inter', 'Roboto', 'Helvetica', 'Arial', sans-serif",
    h1: {
      fontWeight: 700,
    },
    h2: {
      fontWeight: 600,
    },
    h3: {
      fontWeight: 600,
    },
    button: {
      fontWeight: 500,
      textTransform: 'none',
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          padding: '10px 24px',
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
        },
      },
    },
  },
});

const createDarkTheme = () => createTheme({
  palette: {
    mode: 'dark',
    ...darkTheme,
  },
  typography: {
    fontFamily: "'Inter', 'Roboto', 'Helvetica', 'Arial', sans-serif",
    h1: {
      fontWeight: 700,
    },
    h2: {
      fontWeight: 600,
    },
    h3: {
      fontWeight: 600,
    },
    button: {
      fontWeight: 500,
      textTransform: 'none',
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          padding: '10px 24px',
          boxShadow: 'none',
          '&:hover': {
            boxShadow: '0 4px 12px rgba(33, 150, 243, 0.2)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)',
          backgroundColor: darkTheme.background.card,
        },
      },
    },
  },
});

const ThemeContext = createContext<ThemeContextType>({
  mode: 'dark',
  toggleTheme: () => {},
});

export const useTheme = () => useContext(ThemeContext);

interface ThemeProviderProps {
  children: ReactNode;
}

// THE KEY CHANGE IS HERE - making the ThemeProvider a named export
export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  // Default to dark theme for financial applications
  const [mode, setMode] = useState<ThemeMode>('dark');

  // Check if user has a saved preference
  useEffect(() => {
    const savedMode = localStorage.getItem('themeMode') as ThemeMode;
    if (savedMode && (savedMode === 'light' || savedMode === 'dark')) {
      setMode(savedMode);
    } else {
      // Use system preference if no saved preference
      const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
      setMode(prefersDarkMode ? 'dark' : 'light');
    }
  }, []);

  const toggleTheme = () => {
    const newMode = mode === 'light' ? 'dark' : 'light';
    setMode(newMode);
    localStorage.setItem('themeMode', newMode);
  };

  // Select appropriate theme based on mode
  const theme = mode === 'light' ? createLightTheme() : createDarkTheme();

  return (
    <ThemeContext.Provider value={{ mode, toggleTheme }}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};