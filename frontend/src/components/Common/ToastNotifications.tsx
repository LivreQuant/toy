import React from 'react';
import './ToastNotification.css'; // Import styles

interface ToastMessage {
  id: number;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
}

interface ToastNotificationsContainerProps {
  toasts: ToastMessage[];
  removeToast: (id: number) => void;
}

const ToastNotificationsContainer: React.FC<ToastNotificationsContainerProps> = ({ toasts, removeToast }) => {
  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          <span>{toast.message}</span>
          <button onClick={() => removeToast(toast.id)} style={{ background: 'none', border: 'none', color: 'white', marginLeft: '10px', cursor: 'pointer' }}>
            &times;
          </button>
        </div>
      ))}
    </div>
  );
};

export default ToastNotificationsContainer;