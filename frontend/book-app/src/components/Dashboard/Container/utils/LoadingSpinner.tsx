// frontend_dist/book-app/src/components/Dashboard/Container/LoadingSpinner.tsx
import React from 'react';
import { Spinner } from '@blueprintjs/core';

const LoadingSpinner: React.FC = () => {
  return (
    <div style={{
      height: '100%',
      width: '100%',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      backgroundColor: '#f5f5f5'
    }}>
      <Spinner size={50} />
      <div style={{ 
        marginTop: '20px', 
        fontSize: '16px', 
        color: '#666',
        textAlign: 'center'
      }}>
        Loading Trading Dashboard...
      </div>
    </div>
  );
};

export default LoadingSpinner;