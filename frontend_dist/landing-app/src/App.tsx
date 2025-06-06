// landing-app/src/App.tsx
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';

import LandingPage from './pages/LandingPage';
import EnterpriseContactPage from './pages/EnterpriseContactPage';

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <LandingPage />
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;