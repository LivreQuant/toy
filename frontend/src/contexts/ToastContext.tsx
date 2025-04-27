// src/contexts/ToastContext.tsx (Corrected)
import React, { createContext, useState, useCallback, ReactNode, useMemo } from 'react';

import { toastService, ToastConfig } from '../services/notification/toast-service';

import ToastNotificationsContainer from '../components/Common/ToastNotifications';

// ... (Keep ToastMessage interface) ...
interface ToastMessage {
  id: number;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
}
interface ToastContextProps {
  addToast: (type: ToastMessage['type'], message: string, duration?: number) => void;
}

export const ToastContext = createContext<ToastContextProps | undefined>(undefined);
interface ToastProviderProps { children: ReactNode; }
let toastIdCounter = 0;

export const ToastProvider: React.FC<ToastProviderProps> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((type: ToastMessage['type'], message: string, duration: number = 5000) => {
    // ... (addToast implementation) ...
  }, []);
  const removeToast = useCallback((id: number) => { /* ... */ }, []);

  useMemo(() => {
    // Use the correct method name and add type to parameter
    toastService.registerDisplayMethod((toastConfig: ToastConfig) => { // Corrected method and type
        addToast(toastConfig.type, toastConfig.message, toastConfig.duration);
    });
  }, [addToast]);

  const contextValue = useMemo(() => ({ addToast }), [addToast]);

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <ToastNotificationsContainer toasts={toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  );
};