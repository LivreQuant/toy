import React from 'react';

interface LoadingSpinnerProps {
  message?: string;
  size?: number;
  thickness?: number;
  className?: string;
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ 
  message, 
  size = 40, 
  thickness = 4,
  className = 'loading-screen'
}) => {
  const spinnerStyle: React.CSSProperties = {
    width: `${size}px`,
    height: `${size}px`,
    borderWidth: `${thickness}px`,
    borderTopWidth: `${thickness}px`,
  };

  return (
    <div className={className}>
      <div className="loading-spinner" style={spinnerStyle}></div>
      {message && <p className="loading-message">{message}</p>}
    </div>
  );
};

export default LoadingSpinner;