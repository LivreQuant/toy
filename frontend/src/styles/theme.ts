// src/styles/theme.ts
// This file is optional. You can define theme variables here
// if you're using a styling solution like styled-components or Material UI.

export interface AppTheme {
    colors: {
      primary: string;
      secondary: string;
      background: string;
      text: string;
      error: string;
      success: string;
      warning: string;
      // Add more colors as needed
    };
    fonts: {
      main: string;
      code: string;
    };
    // Add other theme properties (spacing, breakpoints, etc.)
  }
  
  export const lightTheme: AppTheme = {
    colors: {
      primary: '#3498db',
      secondary: '#2ecc71',
      background: '#f5f7fa',
      text: '#333333',
      error: '#e74c3c',
      success: '#2ecc71',
      warning: '#f39c12',
    },
    fonts: {
      main: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif",
      code: "source-code-pro, Menlo, Monaco, Consolas, 'Courier New', monospace",
    },
  };
  
  export const darkTheme: AppTheme = {
     colors: {
       primary: '#3498db',
       secondary: '#2ecc71',
       background: '#2c3e50',
       text: '#ecf0f1',
       error: '#e74c3c',
       success: '#2ecc71',
       warning: '#f39c12',
     },
     fonts: {
       main: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif",
       code: "source-code-pro, Menlo, Monaco, Consolas, 'Courier New', monospace",
     },
   };
  
  // Export the default theme (or logic to switch themes)
  export const theme = lightTheme;