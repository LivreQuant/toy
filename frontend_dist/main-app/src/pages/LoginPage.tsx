// src/pages/LoginPage.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import LoginPage from './Auth/LoginPage'; // Import from the correct location

const LoginPageWrapper: React.FC = () => {
  const navigate = useNavigate();

  return <LoginPage />;
};

export default LoginPageWrapper;