// src/components/Demo/ToastDemo.tsx
import React from 'react';
import { useToast } from '../../hooks/useToast';

const ToastDemo: React.FC = () => {
  const { addToast } = useToast();

  return (
    <div className="toast-demo">
      <h2>Toast Notification Demo</h2>
      <div className="toast-buttons">
        <button onClick={() => addToast('success', 'Operation completed successfully!')}>
          Show Success Toast
        </button>
        <button onClick={() => addToast('error', 'An error occurred. Please try again.')}>
          Show Error Toast
        </button>
        <button onClick={() => addToast('warning', 'This action cannot be undone.')}>
          Show Warning Toast
        </button>
        <button onClick={() => addToast('info', 'Your session will expire in 5 minutes.', 10000)}>
          Show Long-Duration Info Toast
        </button>
        <button onClick={() => addToast('info', 'Click the X to dismiss this toast.', 0)}>
          Show Manual Dismiss Toast
        </button>
      </div>
      
      <div className="toast-usage-guide">
        <h3>How to Use Toasts:</h3>
        <pre>{`
// Option 1: Using the useToast hook directly
import { useToast } from '../hooks/useToast';

function MyComponent() {
  const { addToast } = useToast();
  
  const handleAction = () => {
    try {
      // Do something
      addToast('success', 'Operation successful!');
    } catch (error) {
      addToast('error', \`Error: \${error.message}\`);
    }
  };
}

// Option 2: Using the toastService directly (in services/utilities)
import { toastService } from '@trading-app/toast';

function myUtilityFunction() {
  try {
    // Do something
    toastService.success('Operation successful!');
  } catch (error) {
    toastService.error(\`Error: \${error.message}\`);
  }
}
        `}</pre>
      </div>
    </div>
  );
};

export default ToastDemo;