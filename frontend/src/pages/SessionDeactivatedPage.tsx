import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { DeviceIdManager } from '../services/auth/device-id-manager';

const SessionDeactivatedPage: React.FC = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const deviceIdManager = DeviceIdManager.getInstance();

  const handleReactivate = () => {
    // Use the new public method
    deviceIdManager.regenerateDeviceId();
    
    // Redirect to home or login page
    navigate('/home');
  };

  const handleClose = () => {
    // Logout and clear everything
    logout();
  };

  return (
    <div className="session-deactivated-page">
      <h1>Session Deactivated</h1>
      <p>Your current session has been deactivated. This can happen when:</p>
      <ul>
        <li>You logged in on another device</li>
        <li>Your session was terminated</li>
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
          Close Session
        </button>
      </div>
    </div>
  );
};

export default SessionDeactivatedPage;