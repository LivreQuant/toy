// src/components/Auth/Logout.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useConnection } from '../../contexts/ConnectionContext';
import './Logout.css';

interface LogoutProps {
  onLogout?: () => void;
}

const Logout: React.FC<LogoutProps> = ({ onLogout }) => {
  const { disconnect } = useConnection();
  const navigate = useNavigate();
  
  const handleLogout = async () => {
    try {
      const token = localStorage.getItem('token');
      
      if (token) {
        // Optional: Notify server about logout
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
      }
    } catch (err) {
      console.error('Error during logout:', err);
    } finally {
      // Disconnect from session
      disconnect();
      
      // Remove token
      localStorage.removeItem('token');
      
      // Callback if provided
      if (onLogout) {
        onLogout();
      }
      
      // Redirect to login
      navigate('/login');
    }
  };
  
  return (
    <button className="logout-button" onClick={handleLogout}>
      Logout
    </button>
  );
};

export default Logout;