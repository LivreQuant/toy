// src/components/Dashboard/Container/layout/TopNavbar.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom'; // Add this import
import { Button } from '@blueprintjs/core';
import { useConnection } from '../../../../hooks/useConnection';
import { useToast } from '../../../../hooks/useToast';

interface TopNavbarProps {
  onAddView: () => void;
  onSaveLayout: () => void;
  configServiceReady: boolean;
  bookId?: string;
}

const TopNavbar: React.FC<TopNavbarProps> = ({
  onAddView,
  onSaveLayout,
  configServiceReady,
  bookId
}) => {
  const navigate = useNavigate(); // Add this
  const { connectionManager, connectionState } = useConnection();
  const { addToast } = useToast();
  
  const isSimulatorRunning = connectionState?.simulatorStatus === 'RUNNING';
  const isSimulatorBusy = connectionState?.simulatorStatus === 'STARTING' || 
                         connectionState?.simulatorStatus === 'STOPPING';

  const handleBackToBookDetails = async () => {
    // If simulator is running, shut it down first
    if (isSimulatorRunning && connectionManager) {
      addToast('info', 'Shutting down simulator...');
      
      try {
        const result = await connectionManager.stopSimulator();
        
        if (result.success) {
          addToast('success', 'Simulator shut down successfully');
        } else {
          addToast('warning', `Simulator shutdown had issues: ${result.error || 'Unknown error'}`);
        }
      } catch (error: any) {
        addToast('error', `Error shutting down simulator: ${error.message}`);
      }
      
      // Add a small delay to ensure shutdown completes
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    
    // Navigate back to book details page
    if (bookId) {
      navigate(`/${bookId}`);
    } else {
      // Fallback if no bookId
      navigate(-1); // Go back in history
    }
  };

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
      {/* LEFT SIDE - Back to Book Details */}
      <Button 
        minimal={true} 
        icon="arrow-left" 
        text={isSimulatorRunning ? "Shutdown & Exit Dashboard" : "Back to Book Details"}
        onClick={handleBackToBookDetails}
        disabled={isSimulatorBusy}
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