// src/components/Dashboard/Container/layout/TopNavbar.tsx
import React from 'react';
import { Button } from '@blueprintjs/core';

interface TopNavbarProps {
  onAddView: () => void;
  onSaveLayout: () => void;
  onBackToMain: () => void; // ADD THIS
  configServiceReady: boolean;
  bookId?: string;
}

const TopNavbar: React.FC<TopNavbarProps> = ({
  onAddView,
  onSaveLayout,
  onBackToMain, // ADD THIS
  configServiceReady,
  bookId
}) => {
  return (
    <div style={{
      width: '100%',
      height: '50px',
      backgroundColor: '#30404d',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 20px',
      zIndex: 1000,
      flexShrink: 0,
      borderBottom: '1px solid #404854'
    }}>
      {/* LEFT SIDE - Back to Main App */}
      <Button 
        minimal={true} 
        icon="arrow-left" 
        text="Back to Main App" 
        onClick={onBackToMain} // CHANGED TO USE CALLBACK
        style={{
          color: '#ffffff',
          fontSize: '14px'
        }}
      />

      {/* RIGHT SIDE - Dashboard Controls */}
      <div style={{ display: 'flex', gap: '10px' }}>
        <Button 
          minimal={true} 
          icon="add-to-artifact" 
          text="Add View" 
          onClick={onAddView}
          style={{
            color: '#ffffff',
            fontSize: '14px'
          }}
        />
        <Button 
          minimal={true} 
          icon="floppy-disk" 
          text="Save Layout" 
          onClick={onSaveLayout}
          disabled={!configServiceReady}
          style={{
            color: '#ffffff',
            fontSize: '14px'
          }}
        />
      </div>
    </div>
  );
};

export default TopNavbar;