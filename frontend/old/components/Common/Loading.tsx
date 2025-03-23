// src/components/Common/Loading.tsx
import React from 'react';
import './Loading.css';

interface LoadingProps {
  size?: 'small' | 'medium' | 'large';
  message?: string;
  fullscreen?: boolean;
}

const Loading: React.FC<LoadingProps> = ({ 
  size = 'medium', 
  message = 'Loading...', 
  fullscreen = false 
}) => {
  const containerClass = fullscreen 
    ? 'loading-container fullscreen' 
    : 'loading-container';
  
  return (
    <div className={containerClass}>
      <div className={`loading-spinner ${size}`}>
        <div className="spinner-circle"></div>
      </div>
      {message && <p className="loading-message">{message}</p>}
    </div>
  );
};

export default Loading;