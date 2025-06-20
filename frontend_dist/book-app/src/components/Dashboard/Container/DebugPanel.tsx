// frontend_dist/book-app/src/components/Dashboard/Container/DebugPanel.tsx
import React from 'react';
import { Views } from './layoutTypes';

interface DebugPanelProps {
  onTestCustomModal: () => void;
  onAddView: () => void;
  onTestQuestionDialog: () => void;
  onTestViewNameDialog: () => void;
  onTestColumnChooser: () => void;
  availableViews: number;
  bookId: string;
  configServiceReady: boolean;
}

const DebugPanel: React.FC<DebugPanelProps> = ({
  onTestCustomModal,
  onAddView,
  onTestQuestionDialog,
  onTestViewNameDialog,
  onTestColumnChooser,
  availableViews,
  bookId,
  configServiceReady
}) => {
  // Don't render in production
  if (process.env.NODE_ENV === 'production') {
    return null;
  }

  return (
    <div style={{ 
      backgroundColor: '#ffe6e6', 
      padding: '10px', 
      fontSize: '12px',
      borderBottom: '1px solid #ccc',
      display: 'flex',
      gap: '10px',
      flexWrap: 'wrap',
      alignItems: 'center',
      flexShrink: 0
    }}>
      <span>🐛 DEBUG MODALS:</span>
      <button 
        onClick={onTestCustomModal} 
        style={{ 
          padding: '4px 8px', 
          fontSize: '11px', 
          backgroundColor: '#4CAF50', 
          color: 'white', 
          border: 'none', 
          borderRadius: '3px' 
        }}
      >
        Test Custom Modal
      </button>
      <button 
        onClick={onAddView} 
        style={{ 
          padding: '4px 8px', 
          fontSize: '11px', 
          backgroundColor: '#FF5722', 
          color: 'white', 
          border: 'none', 
          borderRadius: '3px' 
        }}
      >
        Test Add View Modal
      </button>
      <button 
        onClick={onTestQuestionDialog} 
        style={{ 
          padding: '4px 8px', 
          fontSize: '11px', 
          backgroundColor: '#2196F3', 
          color: 'white', 
          border: 'none', 
          borderRadius: '3px' 
        }}
      >
        Test Blueprint Question
      </button>
      <button 
        onClick={onTestViewNameDialog} 
        style={{ 
          padding: '4px 8px', 
          fontSize: '11px', 
          backgroundColor: '#FF9800', 
          color: 'white', 
          border: 'none', 
          borderRadius: '3px' 
        }}
      >
        Test Blueprint ViewName
      </button>
      <button 
        onClick={onTestColumnChooser} 
        style={{ 
          padding: '4px 8px', 
          fontSize: '11px', 
          backgroundColor: '#9C27B0', 
          color: 'white', 
          border: 'none', 
          borderRadius: '3px' 
        }}
      >
        Test Blueprint Column
      </button>
      <span style={{ marginLeft: '20px' }}>STATUS:</span>
      <span>Available Views: {availableViews}</span>
      <span>Book ID: {bookId}</span>
      <span>Config Service: {configServiceReady ? '✅ Ready' : '❌ Not Ready'}</span>
    </div>
  );
};

export default DebugPanel;