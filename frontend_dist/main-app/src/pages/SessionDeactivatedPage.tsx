// src/pages/SessionDeactivatedPage.tsx
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authState } from '../state/auth-state';
import { toastService } from '../services/notification/toast-service';
import './SessionDeactivatedPage.css';

const SessionDeactivatedPage: React.FC = () => {
  const navigate = useNavigate();

  // Check if the user should be here
  useEffect(() => {
    const state = authState.getState();
    // If not authenticated at all, redirect to login
    if (!state.isAuthenticated) {
      navigate('/login', { replace: true });
    }
  }, [navigate]);

  // Added function to close the window
  const handleCloseWindow = () => {
    // Close the current window/tab
    window.close();
    
    // Fallback if window.close() doesn't work (due to browser restrictions)
    // Some browsers only allow window.close() for windows opened by JavaScript
    setTimeout(() => {
      // Show message if window didn't close, using toast instead of alert
      toastService.warning('Please close this tab manually. This session has been deactivated.', 0); // 0 for manual dismiss
    }, 300);
  };

  return (
    <div className="session-deactivated-page">
      <h1>Session Deactivated</h1>
      <p>Your current session has been deactivated. This can happen when:</p>
      <ul>
        <li>Your session was opened on another device</li>
        <li>Your session has expired or been terminated</li>
        <li>Your device ID is no longer recognized by the server</li>
      </ul>

      <div className="session-actions">
        <button 
          onClick={handleCloseWindow} 
          className="close-window-button"
        >
          Close Window
        </button>
      </div>
    </div>
  );
};

export default SessionDeactivatedPage;