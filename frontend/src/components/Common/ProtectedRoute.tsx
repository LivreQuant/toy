// src/components/Common/ProtectedRoute.tsx
import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useTokenManager } from '../../hooks/useTokenManager';
import LoadingSpinner from './LoadingSpinner';

interface ProtectedRouteProps {
  children: React.ReactElement;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isAuthLoading } = useAuth();
  const tokenManager = useTokenManager();

  if (isAuthLoading) {
    return <LoadingSpinner message="Checking authentication..." />;
  }

  // Check for deactivated session
  if (isAuthenticated && tokenManager.isSessionDeactivated()) {
    return <Navigate to="/session-deactivated" replace />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

export default ProtectedRoute;