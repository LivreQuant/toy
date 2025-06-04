import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom'; // Assuming react-router-dom
import { useAuth } from './useAuth';

export const useRequireAuth = (redirectTo: string = '/login') => {
  const { isAuthenticated, isAuthLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // Only redirect if loading is finished and user is not authenticated
    if (!isAuthLoading && !isAuthenticated) {
      navigate(redirectTo, { replace: true });
    }
  }, [isAuthenticated, isAuthLoading, navigate, redirectTo]);

  // Optionally return loading/auth state if needed by the component
  return { isAuthenticated, isAuthLoading };
};