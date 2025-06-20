// frontend_dist/book-app/src/components/Dashboard/Container/BottomNavbar.tsx
import React from 'react';
import { Alignment, Button, Navbar } from '@blueprintjs/core';

interface BottomNavbarProps {
  bookId: string;
  onCancelAllConvictions: () => void;
}

const BottomNavbar: React.FC<BottomNavbarProps> = ({
  bookId,
  onCancelAllConvictions
}) => {
  return (
    <Navbar className="bp3-dark" style={{ 
      width: '100%', 
      zIndex: 100,
      flexShrink: 0
    }}>
      <Navbar.Group align={Alignment.LEFT}>
        <Navbar.Heading>trader@{bookId}</Navbar.Heading>
        <Navbar.Divider />
      </Navbar.Group>
      <Navbar.Group align={Alignment.RIGHT}>
        <Button 
          minimal={true} 
          icon="delete" 
          text="Cancel All Desk Convictions" 
          onClick={onCancelAllConvictions} 
        />
      </Navbar.Group>
    </Navbar>
  );
};

export default BottomNavbar;