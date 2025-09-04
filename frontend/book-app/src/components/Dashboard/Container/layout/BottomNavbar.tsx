// src/components/Dashboard/Container/layout/BottomNavbar.tsx
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
    <div style={{
      width: '100%',
      height: '50px',
      backgroundColor: 'white',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 20px',
      zIndex: 1000,
      flexShrink: 0,
      borderTop: '1px solid #404854'
    }}>
      {/* LEFT SIDE - Trading Info */}
      <div style={{ 
        color: 'black', 
        fontSize: '14px',
        fontWeight: 500
      }}>
        Trading Book: {bookId}
      </div>

      {/* RIGHT SIDE - Actions */}
      <Button 
        minimal={true} 
        icon="delete" 
        text="Cancel All Convictions" 
        onClick={onCancelAllConvictions}
        intent="danger"
        style={{
          color: '#ffffff',
          fontSize: '14px'
        }}
      />
    </div>
  );
};

export default BottomNavbar;