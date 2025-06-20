// frontend_dist/book-app/src/components/Dashboard/Container/TopNavbar.tsx
import React from 'react';
import { Alignment, Button, Navbar } from '@blueprintjs/core';

interface TopNavbarProps {
  onAddView: () => void;
  onSaveLayout: () => void;
  configServiceReady: boolean;
}

const TopNavbar: React.FC<TopNavbarProps> = ({
  onAddView,
  onSaveLayout,
  configServiceReady
}) => {
  return (
    <Navbar className="bp3-dark" style={{ 
      width: '100%', 
      zIndex: 100,
      flexShrink: 0
    }}>
      <Navbar.Group align={Alignment.LEFT}>
        <Navbar.Heading>Trading Dashboard</Navbar.Heading>
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