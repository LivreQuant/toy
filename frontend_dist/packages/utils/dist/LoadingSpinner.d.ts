import React from 'react';
import './LoadingScreen.css';
interface LoadingSpinnerProps {
    message?: string;
    size?: number;
    thickness?: number;
}
declare const LoadingSpinner: React.FC<LoadingSpinnerProps>;
export default LoadingSpinner;
