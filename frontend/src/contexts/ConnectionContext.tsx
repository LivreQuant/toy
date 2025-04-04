// src/contexts/ConnectionContext.tsx
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { ConnectionManager, ConnectionState } from '../services/connection/connection-manager';
import { TokenManager } from '../services/auth/token-manager';
import { useAuth } from './AuthContext';
import { SessionManager } from '../services/session/session-manager';
import { toastService } from '../services/notification/toast-service';

interface ConnectionContextType {
  connectionManager: ConnectionManager;
  connectionState: ConnectionState;
  connect: () => Promise<boolean>;
  disconnect: () => void;
  reconnect: () => Promise<boolean>;
  isConnected: boolean;
  isConnecting: boolean;
  isRecovering: boolean;
  recoveryAttempt: number;
  connectionQuality: string;
  error: string | null;

  startSimulator: (options?: { initialSymbols?: string[], initialCash?: number }) => Promise<{ success: boolean; status?: string; error?: string }>;
  stopSimulator: () => Promise<{ success: boolean; error?: string }>;

  submitOrder: (order: any) => Promise<any>;
  exchangeData: any;
  manualReconnect: () => Promise<boolean>;
}

const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

export const ConnectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { tokenManager, isAuthenticated } = useAuth();
  const [connectionManager] = useState<ConnectionManager>(() => 
    new ConnectionManager(tokenManager)
  );
  
  const [connectionState, setConnectionState] = useState<ConnectionState>(connectionManager.getState());
  const [exchangeData, setExchangeData] = useState<any>({});
  
  const [isRecovering, setIsRecovering] = useState<boolean>(false);
  const [recoveryAttempt, setRecoveryAttempt] = useState<number>(0);
  
  useEffect(() => {
    const handleStateChange = ({ current }: { current: ConnectionState }) => {
      setConnectionState(current);
    };
    
    const handleExchangeData = (data: any) => {
      console.log('Received Exchange Data:', data);
      setExchangeData(data);
    };
    
    const handleRecoveryAttempt = (data: any) => {
      setIsRecovering(true);
      setRecoveryAttempt(data.attempt);
    };
    
    const handleRecoverySuccess = () => {
      setIsRecovering(false);
      setRecoveryAttempt(0);
    };
    
    const handleRecoveryFailed = () => {
      setIsRecovering(false);
    };
    
    connectionManager.on('state_change', handleStateChange);
    connectionManager.on('exchange_data', handleExchangeData);
    
    connectionManager.on('recovery_attempt', handleRecoveryAttempt);
    connectionManager.on('recovery_success', handleRecoverySuccess);
    connectionManager.on('recovery_failed', handleRecoveryFailed);
    
    if (isAuthenticated && !connectionState.isConnected && !connectionState.isConnecting) {
      connectionManager.connect().catch(err => {
        console.error('Failed to auto-connect after authentication:', err);
      });
    } else if (!isAuthenticated && (connectionState.isConnected || connectionState.isConnecting)) {
      connectionManager.disconnect();
    }
    
    return () => {
      connectionManager.off('state_change', handleStateChange);
      connectionManager.off('exchange_data', handleExchangeData);
      connectionManager.off('recovery_attempt', handleRecoveryAttempt);
      connectionManager.off('recovery_success', handleRecoverySuccess);
      connectionManager.off('recovery_failed', handleRecoveryFailed);
    };
  }, [connectionManager, isAuthenticated, connectionState.isConnected, connectionState.isConnecting]);
  
  const connect = async () => {
    if (!isAuthenticated) {
      console.warn('Cannot connect - user is not authenticated');
      return false;
    }
    return connectionManager.connect();
  };
  
  const disconnect = () => {
    connectionManager.disconnect();
  };
  
  const reconnect = async () => {
    if (!isAuthenticated) {
      console.warn('Cannot reconnect - user is not authenticated');
      return false;
    }
    return connectionManager.reconnect();
  };

  const manualReconnect = useCallback(async () => {
    if (connectionManager.attemptRecovery) {
      return connectionManager.attemptRecovery('manual_user_request');
    } else {
      return reconnect();
    }
  }, [connectionManager, reconnect]);
  
  const startSimulator = async (options: {
    initialSymbols?: string[],
    initialCash?: number
  } = {}) => {
    if (!isAuthenticated || !connectionState.isConnected) {
      console.warn('Cannot start simulator - user is not authenticated or not connected');
      return { success: false, error: 'Not authenticated or connected' };
    }
    return connectionManager.startSimulator(options);
  };
    
  const stopSimulator = async () => {
    if (!isAuthenticated || !connectionState.isConnected) {
      console.warn('Cannot stop simulator - user is not authenticated or not connected');
      return { success: false, error: 'Not authenticated or connected' };
    }
    return connectionManager.stopSimulator();
  };
  
  const submitOrder = async (order: any) => {
    if (!isAuthenticated || !connectionState.isConnected) {
      return { success: false, error: 'Not authenticated or connected' };
    }
    return connectionManager.submitOrder(order);
  };
  
  return (
    <ConnectionContext.Provider value={{
      connectionManager,
      connectionState,
      connect,
      disconnect,
      reconnect,
      isConnected: connectionState.isConnected,
      isConnecting: connectionState.isConnecting,
      isRecovering,
      recoveryAttempt,
      connectionQuality: connectionState.connectionQuality,
      error: connectionState.error,
      startSimulator,
      stopSimulator,
      submitOrder,
      exchangeData,
      manualReconnect
    }}>
      {children}
    </ConnectionContext.Provider>
  );
};

export const useConnection = (): ConnectionContextType => {
  const context = useContext(ConnectionContext);
  if (context === undefined) {
    throw new Error('useConnection must be used within a ConnectionProvider');
  }
  return context;
};