// src/components/Common/ToastNotifications.tsx
import React, { useState, useEffect, useRef } from 'react';
import './ToastNotification.css';

interface ToastMessage {
  id: number;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
}

interface ToastNotificationsContainerProps {
  toasts: ToastMessage[];
  removeToast: (id: number) => void;
}

interface ToastProps {
  toast: ToastMessage;
  onRemove: () => void;
}

// Individual Toast Component
const Toast: React.FC<ToastProps> = ({ toast, onRemove }) => {
  const [isPaused, setIsPaused] = useState(false);
  const [progress, setProgress] = useState(100);
  const [timeLeft, setTimeLeft] = useState(toast.duration || 5000);
  const progressIntervalRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(Date.now());
  const pausedAtRef = useRef<number>(0);

  // Setup progress bar
  useEffect(() => {
    // Skip for toasts with duration = 0 or undefined (manual dismiss only)
    if (!toast.duration) return;

    const totalDuration = toast.duration;
    const updateInterval = 10; // Update every 10ms for smoother animation

    const startProgress = () => {
      startTimeRef.current = Date.now() - pausedAtRef.current;
      
      progressIntervalRef.current = window.setInterval(() => {
        const elapsedTime = Date.now() - startTimeRef.current;
        const calculatedProgress = 100 - (elapsedTime / totalDuration * 100);
        
        if (calculatedProgress <= 0) {
          if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
          }
          onRemove();
        } else {
          setProgress(calculatedProgress);
          setTimeLeft(totalDuration - elapsedTime);
        }
      }, updateInterval);
    };

    if (!isPaused) {
      startProgress();
    }

    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, [toast.duration, isPaused, onRemove]);

  const handlePause = () => {
    if (isPaused) return; // Don't allow resuming
    
    // Pause
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
      pausedAtRef.current = Date.now() - startTimeRef.current;
    }
    setIsPaused(true);
  };

  // Get title based on toast type
  const getTitle = () => {
    switch (toast.type) {
      case 'success': return 'Success';
      case 'error': return 'Error';
      case 'warning': return 'Warning';
      case 'info': return 'Information';
    }
  };

  // Get icon based on toast type
  const getIcon = () => {
    switch (toast.type) {
      case 'success': return '✓';
      case 'error': return '✕';
      case 'warning': return '⚠';
      case 'info': return 'ℹ';
    }
  };

  // Format time left in seconds
  const formatTimeLeft = () => {
    return `${Math.ceil(timeLeft / 1000)}s`;
  };

  // Check if toast has a duration (not 0 and not undefined)
  const hasAutoExpiry = toast.duration !== undefined && toast.duration > 0;

  return (
    <div className={`toast toast-${toast.type}`}>
      <div className="toast-content">
        <div className="toast-header">
          <div className="toast-title">
            <span className="toast-icon">{getIcon()}</span>
            {getTitle()}
          </div>
          <div className="toast-actions">
            {hasAutoExpiry && !isPaused && (
              <>
                <button 
                  className="toast-pause" 
                  onClick={handlePause}
                  title="Pause timer"
                >
                  ⏸
                </button>
                <span style={{ marginRight: '8px', fontSize: '12px', opacity: 0.8 }}>
                  {formatTimeLeft()}
                </span>
              </>
            )}
            <button 
              className="toast-close" 
              onClick={onRemove}
              title="Close"
            >
              ×
            </button>
          </div>
        </div>
        <div className="toast-message">{toast.message}</div>
      </div>
      
      {hasAutoExpiry && !isPaused && (
        <div className="toast-progress">
          <div 
            className="toast-progress-bar" 
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
};

const ToastNotificationsContainer: React.FC<ToastNotificationsContainerProps> = ({ 
  toasts, 
  removeToast 
}) => {
  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <Toast 
          key={toast.id} 
          toast={toast} 
          onRemove={() => removeToast(toast.id)} 
        />
      ))}
    </div>
  );
};

export default ToastNotificationsContainer;