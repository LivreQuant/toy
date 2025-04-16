// In src/pages/SessionDeactivatedPage.tsx
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { DeviceIdManager } from '../services/auth/device-id-manager';
import { appState } from '../services/state/app-state.service';

const SessionDeactivatedPage: React.FC = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const deviceIdManager = DeviceIdManager.getInstance();

  // Check if the user should be here
  useEffect(() => {
    const authState = appState.getState().auth;
    // If not authenticated at all, redirect to login
    if (!authState.isAuthenticated) {
      navigate('/login', { replace: true });
    }
  }, [navigate]);

  const handleReactivate = () => {
    // Regenerate device ID
    deviceIdManager.regenerateDeviceId();
    
    // Redirect to home
    navigate('/home');
  };

  const handleClose = () => {
    // Logout completely
    logout();
    // Navigation handled by auth context after logout
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
          onClick={handleReactivate} 
          className="reactivate-button"
        >
          Reactivate Session
        </button>
        <button 
          onClick={handleClose} 
          className="close-button"
        >
          Log Out
        </button>
      </div>
    </div>
  );
};

export default SessionDeactivatedPage;