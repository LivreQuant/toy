import React from 'react';
import './LoadingScreen.css'; // Reuse the loading screen styles if applicable or create new ones

interface LoadingSpinnerProps {
  message?: string;
  size?: number; // Optional size in pixels
  thickness?: number; // Optional border thickness
}

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ message, size = 40, thickness = 4 }) => {
  const spinnerStyle: React.CSSProperties = {
    width: `${size}px`,
    height: `${size}px`,
    borderWidth: `${thickness}px`,
    borderTopWidth: `${thickness}px`, // Ensure top border is also set
  };

  return (
    <div className="loading-screen"> {/* You might want a more specific container class */}
      <div className="loading-spinner" style={spinnerStyle}></div>
      {message && <p className="loading-message">{message}</p>}
    </div>
  );
};

export default LoadingSpinner;