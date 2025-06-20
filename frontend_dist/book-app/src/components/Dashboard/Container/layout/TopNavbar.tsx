// frontend_dist/book-app/src/components/Dashboard/Container/TopNavbar.tsx
import React from 'react';
import { Alignment, Button, Navbar } from '@blueprintjs/core';
import { config } from '@trading-app/config';

interface TopNavbarProps {
  onAddView: () => void;
  onSaveLayout: () => void;
  configServiceReady: boolean;
  bookId?: string; // Add bookId prop
}

const TopNavbar: React.FC<TopNavbarProps> = ({
  onAddView,
  onSaveLayout,
  configServiceReady,
  bookId
}) => {
  const handleBackToMainApp = () => {
    const mainAppUrl = config.gateway.baseUrl + '/app';
    window.location.href = mainAppUrl;
  };

  return (
    <Navbar className="bp3-dark" style={{ 
      width: '100%', 
      zIndex: 100,
      flexShrink: 0
    }}>
      <Navbar.Group align={Alignment.LEFT}>
        {/* Back to Main App Button */}
        <Button 
          minimal={true} 
          icon="arrow-left" 
          text="Back to Main App" 
          onClick={handleBackToMainApp}
        />
        <Navbar.Divider />
        
        <Navbar.Heading>
          Trading Dashboard {bookId && `- ${bookId}`}
        </Navbar.Heading>
        <Navbar.Divider />
        
        <Button 
          minimal={true} 
          icon="add-to-artifact" 
          text="Add View..." 
          onClick={onAddView}
        />
        <Button 
          minimal={true} 
          icon="floppy-disk" 
          text="Save Layout" 
          onClick={onSaveLayout}
          disabled={!configServiceReady}
        />
      </Navbar.Group>
    </Navbar>
  );
};

export default TopNavbar;