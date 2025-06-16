// src/contexts/ToastContext.tsx
import React, { createContext, useState, useCallback, ReactNode, useMemo, useEffect } from 'react';
import { toastService, ToastConfig } from '@trading-app/toast';
import ToastNotificationsContainer from '../components/Common/ToastNotifications';

// Define the toast message structure
interface ToastMessage {
  id: number; // Internal auto-increment ID for React keys
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
  toastId?: string; // Store the optional toast ID for tracking duplicates
}

// Context interface
interface ToastContextProps {
  addToast: (type: ToastMessage['type'], message: string, duration?: number, id?: string) => void;
}

export const ToastContext = createContext<ToastContextProps | undefined>(undefined);

interface ToastProviderProps { 
  children: ReactNode; 
}

// Counter for unique toast IDs
let toastIdCounter = 0;

export const ToastProvider: React.FC<ToastProviderProps> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  // Add a new toast
  const addToast = useCallback((type: ToastMessage['type'], message: string, duration: number = 5000, toastId?: string) => {
    const id = toastIdCounter++;
    
    setToasts(current => [...current, { id, type, message, duration, toastId }]);
    
    // Auto-remove toast after duration (if not 0)
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  }, []);

  // Remove a toast by ID
  const removeToast = useCallback((id: number) => {
    setToasts(current => current.filter(toast => toast.id !== id));
  }, []);

  // Register the toast display method with the service
  useEffect(() => {
    toastService.registerDisplayMethod((config: ToastConfig) => {
      addToast(config.type, config.message, config.duration, config.id);
    });
    
    // Return cleanup function (though we don't have an unregister method currently)
    return () => {};
  }, [addToast]);

  const contextValue = useMemo(() => ({ addToast }), [addToast]);

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <ToastNotificationsContainer toasts={toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  );
};