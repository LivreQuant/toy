import React, { useEffect } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useTokenManager } from '../../hooks/useTokenManager';
import { DeviceIdManager } from '@trading-app/auth';
import { LoadingSpinner } from '@trading-app/ui'; // ← Changed to named import

interface ProtectedRouteProps {
  children: React.ReactElement;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isAuthLoading } = useAuth();
  const tokenManager = useTokenManager();
  const navigate = useNavigate();

  // Check device ID on mount and when auth status changes
  useEffect(() => {
    if (isAuthenticated) {
      const deviceIdManager = DeviceIdManager.getInstance();
      if (!deviceIdManager.hasStoredDeviceId()) {
        console.log("Device ID missing, redirecting to session deactivated page");
        navigate('/session-deactivated', { replace: true });
      }
    }
  }, [isAuthenticated, navigate]);

  if (isAuthLoading) {
    return <LoadingSpinner message="Checking authentication..." />;
  }

  // This check is already in your code, ensure it works
  if (isAuthenticated && tokenManager.isSessionDeactivated()) {
    return <Navigate to="/session-deactivated" replace />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

export default ProtectedRoute;