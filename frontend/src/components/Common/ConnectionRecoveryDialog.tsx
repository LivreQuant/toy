// src/components/Common/ConnectionRecoveryDialog.tsx
import React from 'react';
// Import the hook to use the connection context
import { useConnection } from '../../contexts/ConnectionContext'; // Adjust path if needed
// Import the ConnectionStatus enum to check against overallStatus
import { ConnectionStatus } from '../../services/connection/unified-connection-state'; // Adjust path if needed
import './ConnectionRecoveryDialog.css';

// Assuming ConnectionRecoveryDialogProps is defined elsewhere or not needed
// interface ConnectionRecoveryDialogProps {}

const ConnectionRecoveryDialog: React.FC = () => {
  // --- Refactored: Destructure properties/methods from the updated context ---
  // Get the necessary state values and the manualReconnect action.
  const {
    isConnected,      // Still useful to check if connection succeeded elsewhere
    isConnecting,     // Check if a connection attempt is in progress
    isRecovering,     // Check if an automatic recovery attempt is in progress
    recoveryAttempt,  // Get the current recovery attempt number
    manualReconnect,  // Get the function to trigger a manual reconnect
    overallStatus     // Get the overall status (e.g., DISCONNECTED)
  } = useConnection();

  // --- Determine if the dialog should be shown ---
  // Example logic: Show if explicitly disconnected AND not currently trying to connect or recover automatically.
  // You might refine this based on specific needs, e.g., show after a certain number of failed recovery attempts.
  const showDialog = overallStatus === ConnectionStatus.DISCONNECTED && !isConnecting && !isRecovering;

  // If the conditions to show the dialog aren't met, render nothing.
  if (!showDialog) {
    return null;
  }

  // --- Event Handlers ---
  // Calls the manualReconnect function obtained from the context.
  const handleRetry = () => {
    // No need to check isConnected here, manualReconnect likely handles it
    manualReconnect();
  };

  // Reloads the entire application page.
  const handleReload = () => {
      window.location.reload();
  }

  return (
    <div className="recovery-dialog-overlay">
      <div className="recovery-dialog">
        <div className="recovery-dialog-header">
          <h2>Connection Lost</h2>
        </div>
        <div className="recovery-dialog-content">
          <p>Connection to the server was lost.</p>
          {/* Display recovery attempts if any occurred */}
          {recoveryAttempt > 0 && <p>Attempted to reconnect {recoveryAttempt} times automatically.</p>}
          <p>You can try reconnecting manually or reload the application.</p>
        </div>
        <div className="recovery-dialog-footer">
           {/* Button to reload the page */}
           <button className="reload-button" onClick={handleReload}>Reload App</button>
           {/* Button to trigger a manual reconnect attempt */}
           <button
              className="retry-button"
              onClick={handleRetry}
              // Disable the button if a connection or recovery attempt is already in progress
              disabled={isConnecting || isRecovering}
           >
              Retry Connection
           </button>
        </div>
      </div>
    </div>
  );
};

export default ConnectionRecoveryDialog;
