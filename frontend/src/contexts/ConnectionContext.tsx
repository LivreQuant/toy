// src/contexts/ConnectionContext.tsx
import React, {
  createContext,
  ReactNode,
  useMemo,
  useEffect,
  useState,
  useContext,
} from 'react';
import { ConnectionManager } from '../services/connection/connection-manager';
// Import AppState type, appState instance, AND necessary Enums/initial state structure
import {
  appState,
  AppState,
  ConnectionStatus,
  initialState as appInitialState, // Rename imported initialState to avoid conflict
} from '../services/state/app-state.service';
import { Subscription } from 'rxjs';
import { getLogger } from '../boot/logging';
import LoadingSpinner from '../components/Common/LoadingSpinner'; // Keep LoadingSpinner
import { useAuth } from '../hooks/useAuth'; // *** Import useAuth ***

// Define the shape of your context data
interface ConnectionContextValue {
  connectionManager: ConnectionManager; // Provide the instance directly
  connectionState: AppState['connection']; // Provide reactive state
  isConnected: boolean;
  isConnecting: boolean; // Combined connecting/recovering for UI simplicity
  isRecovering: boolean; // Specific recovery state
}

// Create the context
export const ConnectionContext = createContext<ConnectionContextValue | undefined>(
  undefined
);

interface ConnectionProviderProps {
  children: ReactNode;
  connectionManager: ConnectionManager; // Pass the instance from App.tsx
}

const logger = getLogger('ConnectionContext');

export const ConnectionProvider: React.FC<ConnectionProviderProps> = ({
  children,
  connectionManager,
}) => {
  // *** Use Auth State ***
  const { isAuthenticated, isAuthLoading } = useAuth();

  // Local state holds the connection slice from AppState
  const [connectionState, setConnectionState] = useState<
    AppState['connection']
  >(() => appState.getState().connection); // Initialize with current state

  // --- Subscribe to Connection State Changes ---
  useEffect(() => {
    logger.info(
      'ConnectionProvider subscribing to AppState connection changes.'
    );
    // Subscribe to the specific connection state slice
    const stateSubscription: Subscription = appState
      .select((s) => s.connection) // Use select for distinct emissions
      .subscribe({
        next: (connState) => {
          // logger.debug('Received connection state update', connState); // Optional: debug logging
          setConnectionState(connState);
        },
        error: (err) => {
          logger.error('Error subscribing to connection state', { error: err });
        },
      });

    return () => {
      logger.info('ConnectionProvider unsubscribing from connection state.');
      stateSubscription.unsubscribe();
    };
  }, []); // Empty dependency array: subscribe only once on mount

  // --- Effect to Manage Desired Connection State Based on Auth ---
  useEffect(() => {
    // *** WAIT FOR AUTH LOADING ***
    if (isAuthLoading) {
      logger.debug('Auth state is loading, delaying connection decision.');
      // Prevent setting desired state while auth is loading
      return;
    }

    // --- Auth check is complete ---
    logger.debug(
      `Auth check complete. isAuthenticated: ${isAuthenticated}. Setting desired connection state.`
    );
    if (isAuthenticated) {
      // If authenticated, desire connection
      connectionManager.setDesiredState({ connected: true });
      // You might also want to control the simulator state here based on user preferences or app logic
      // Example: connectionManager.setDesiredState({ simulatorRunning: true });
    } else {
      // If not authenticated, ensure desired state is disconnected
      // ConnectionManager's internal sync logic will handle the disconnect if needed
      connectionManager.setDesiredState({
        connected: false,
        simulatorRunning: false,
      });
    }

    // No cleanup needed here as ConnectionManager handles its own state persistence
  }, [isAuthenticated, isAuthLoading, connectionManager]); // Re-run when auth state changes


  // --- Provide Context Value ---
  // Memoize the context value to prevent unnecessary re-renders
  const contextValue = useMemo(() => {
    // Use the latest state, fallback to initial only if somehow null (shouldn't happen with init)
    const currentConnState = connectionState ?? appInitialState.connection;
    // Simplify connecting state for consumers
    const isConnected =
      currentConnState.overallStatus === ConnectionStatus.CONNECTED;
    const isConnecting = // Includes CONNECTING and RECOVERING for UI purposes
      currentConnState.overallStatus === ConnectionStatus.CONNECTING ||
      currentConnState.isRecovering; // Use isRecovering flag directly
    const isRecovering = currentConnState.isRecovering; // Expose specific recovery state

    return {
      connectionManager,
      connectionState: currentConnState,
      isConnected,
      isConnecting,
      isRecovering,
    };
  }, [connectionManager, connectionState]); // Recalculate when state changes


  // --- CONDITIONAL RENDERING ---
  // *** Render loading indicator ONLY while Auth is loading ***
  if (isAuthLoading) {
    // You can return null or a more generic app loading indicator here
    // Using the specific spinner might still show "Initializing connection..."
    // It's often better to have a top-level loading screen in App.tsx controlled by isAuthLoading
    logger.debug('Auth is loading, rendering loading spinner.');
    // Returning null is usually better here, let ProtectedRoute handle loading/redirects
    return null;
    // return <LoadingSpinner message="Authenticating..." />; // Or a more generic message
  }

  // Auth is resolved, provide the context to children
  logger.debug('Auth resolved, rendering ConnectionContext.Provider');
  return (
    <ConnectionContext.Provider value={contextValue}>
      {children}
    </ConnectionContext.Provider>
  );
};

// Custom hook remains the same
export const useConnection = () => {
  const context = useContext(ConnectionContext);
  if (context === undefined) {
    throw new Error('useConnection must be used within a ConnectionProvider');
  }
  return context;
};