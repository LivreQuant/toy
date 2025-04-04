import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useMemo,
  useCallback // Added useCallback
} from 'react';
import { ConnectionManager } from '../services/connection/connection-manager';
// Import the state structure type from UnifiedConnectionState
import { UnifiedConnectionState } from '../services/connection/unified-connection-state';
import { useAuth } from './AuthContext'; // Import useAuth to access connectionManager
import { Logger } from '../utils/logger'; // Import Logger if needed for logging here

// Define the specific type for the connection state object provided by the context
// This uses the return type of ConnectionManager's getState method
type ConnectionStateType = ReturnType<ConnectionManager['getState']>;

// Define the shape of the Connection context
interface ConnectionContextType {
connectionManager: ConnectionManager; // The ConnectionManager instance
connectionState: ConnectionStateType; // The current aggregated connection state
manualReconnect: () => Promise<boolean>; // Function to trigger manual reconnect
}

// Create the context
const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

/**
* Provides connection state and management capabilities to the application.
* Relies on AuthProvider to provide the initialized ConnectionManager instance.
*/
export const ConnectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
// Get the initialized connectionManager instance from the Auth context
// This ensures we use the SAME instance throughout the app
const { connectionManager, isAuthenticated, isLoading: isAuthLoading } = useAuth();
const logger = Logger.getInstance(); // Get logger instance if needed

// State to hold the latest connection state object
const [connectionState, setConnectionState] = useState<ConnectionStateType>(
    () => connectionManager.getState() // Initialize with current state
);

// Effect to subscribe to connection state changes
useEffect(() => {
  logger.info("ConnectionContext: Subscribing to state changes.");

  // Handler function to update local state when ConnectionManager emits changes
  const handleStateChange = (newState: { current: ConnectionStateType }) => {
    // Log state changes for debugging if needed (can be verbose)
    // logger.info("ConnectionContext: Received state update", newState.current);
    setConnectionState(newState.current);
  };

  // Subscribe to the state_change event
  connectionManager.on('state_change', handleStateChange);

  // Log the initial state when the context mounts or connectionManager changes
  // logger.info("ConnectionContext: Initial state", connectionManager.getState());

  // Cleanup function to unsubscribe when the component unmounts
  return () => {
    logger.info("ConnectionContext: Unsubscribing from state changes.");
    connectionManager.off('state_change', handleStateChange);
  };
}, [connectionManager, logger]); // Re-run effect if connectionManager instance changes (shouldn't normally)

 // Effect to attempt connection automatically when authentication is ready
 useEffect(() => {
     // Only attempt connect if:
     // 1. Auth is not loading anymore
     // 2. User is authenticated
     // 3. Connection is currently disconnected (avoid redundant connects)
     if (!isAuthLoading && isAuthenticated && connectionState.overallStatus === 'disconnected') {
         logger.info("ConnectionContext: Auth ready and disconnected, attempting auto-connect...");
         connectionManager.connect().catch(err => {
             logger.error("ConnectionContext: Auto-connect attempt failed.", err);
         });
     } else if (!isAuthLoading && !isAuthenticated && connectionState.overallStatus !== 'disconnected') {
         // If auth is ready but user is not authenticated, ensure disconnection
         logger.info("ConnectionContext: Auth ready but not authenticated, ensuring disconnection.");
         connectionManager.disconnect('auth_context_logout');
     }
 }, [isAuthenticated, isAuthLoading, connectionManager, connectionState.overallStatus, logger]); // Dependencies


// --- Manual Reconnect Function ---
// Use useCallback to memoize the function instance
const manualReconnect = useCallback(async (): Promise<boolean> => {
    logger.warn("ConnectionContext: Manual reconnect triggered.");
    toastService.info("Attempting to reconnect..."); // Provide immediate feedback
    try {
        const success = await connectionManager.manualReconnect();
        if (success) {
            toastService.success("Reconnected successfully!");
        } else {
            // Error handling/toast is likely done within ConnectionManager/RecoveryManager
            // toastService.error("Reconnect failed. Please check connection or try again later.");
        }
        return success;
    } catch (error: any) {
        logger.error("ConnectionContext: Manual reconnect failed.", { error: error.message });
        toastService.error(`Reconnect failed: ${error.message}`);
        return false;
    }
}, [connectionManager]); // Dependency: connectionManager instance


// --- Context Value ---
// Memoize the context value to optimize performance
const contextValue = useMemo(() => ({
    connectionManager,
    connectionState,
    manualReconnect
}), [connectionManager, connectionState, manualReconnect]); // Include memoized function

return (
  <ConnectionContext.Provider value={contextValue}>
    {children}
  </ConnectionContext.Provider>
);
};

/**
* Custom hook to easily access the ConnectionContext.
* Ensures the hook is used within a component wrapped by ConnectionProvider.
*/
export const useConnection = (): ConnectionContextType => {
const context = useContext(ConnectionContext);
if (context === undefined) {
  // This usually means ConnectionProvider is missing higher up the component tree
  throw new Error('useConnection must be used within a ConnectionProvider');
}
return context;
};
