// src/components/Auth/Logout.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useConnection } from '../../contexts/ConnectionContext';
import './Logout.css';

interface LogoutProps {
  onLogout?: () => void;
}

const Logout: React.FC<LogoutProps> = ({ onLogout }) => {
  const { logout } = useConnection();
  const navigate = useNavigate();
  
  const handleLogout = async () => {
    // Call the logout method from ConnectionContext
    logout();
    
    // Callback if provided
    if (onLogout) {
      onLogout();
    }
    
    // Redirect to login
    navigate('/login');
  };
  
  return (
    <button className="logout-button" onClick={handleLogout}>
      Logout
    </button>
  );
};

export default Logout;