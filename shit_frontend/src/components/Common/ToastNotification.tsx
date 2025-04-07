// src/components/Common/ToastNotification.tsx
import React, { useState, useEffect } from 'react';
import './ToastNotification.css';

export interface ToastMessage {
  id?: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
}

interface ToastNotificationProps {
  messages: ToastMessage[];
  onRemove: (id: string) => void;
}

const ToastNotification: React.FC<ToastNotificationProps> = ({ 
  messages, 
  onRemove 
}) => {
  return (
    <div className="toast-container">
      {messages.map((toast) => (
        <div 
          key={toast.id} 
          className={`toast toast-${toast.type}`}
        >
          {toast.message}
          <button 
            className="toast-close"
            onClick={() => toast.id && onRemove(toast.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
};

export default ToastNotification;