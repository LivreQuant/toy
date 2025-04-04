// src/contexts/ConnectionContext.tsx

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { ConnectionManager, ConnectionState } from '../services/connection/connection-manager';
import { TokenManager } from '../services/auth/token-manager';
import { useAuth } from './AuthContext';
import { config } from '../config';
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
  marketData: Record<string, any>;
  orders: Record<string, any>;
  portfolio: any;
  streamMarketData: (symbols: string[]) => Promise<boolean>;
  manualReconnect: () => Promise<boolean>;
}

const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

export const ConnectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { tokenManager, isAuthenticated } = useAuth();
  const [connectionManager] = useState<ConnectionManager>(() => 
    new ConnectionManager(tokenManager)
  );
  
  const [connectionState, setConnectionState] = useState<ConnectionState>(connectionManager.getState());
  const [marketData, setMarketData] = useState<Record<string, any>>({});
  const [orders, setOrders] = useState<Record<string, any>>({});
  const [portfolio, setPortfolio] = useState<any>(null);
  
  // Add new state for recovery tracking
  const [isRecovering, setIsRecovering] = useState<boolean>(false);
  const [recoveryAttempt, setRecoveryAttempt] = useState<number>(0);
  
  useEffect(() => {
    // Handle connection state changes
    const handleStateChange = ({ current }: { current: ConnectionState }) => {
      setConnectionState(current);
    };
    
    const handleMarketData = (data: any) => {
      console.log('Connection Context - Received Market Data:', data);
      setMarketData(data);
    };
    
    const handleOrders = (data: any) => {
      setOrders(data);
    };
    
    const handlePortfolio = (data: any) => {
      setPortfolio(data);
    };
    
    // Add recovery event listeners
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
    connectionManager.on('market_data', handleMarketData);
    connectionManager.on('orders', handleOrders);
    connectionManager.on('portfolio', handlePortfolio);
    
    // Register recovery event listeners
    connectionManager.on('recovery_attempt', handleRecoveryAttempt);
    connectionManager.on('recovery_success', handleRecoverySuccess);
    connectionManager.on('recovery_failed', handleRecoveryFailed);
    
    // Only attempt connection when authenticated
    if (isAuthenticated && !connectionState.isConnected && !connectionState.isConnecting) {
      // Connect automatically when authenticated and not already connected/connecting
      connectionManager.connect().catch(err => {
        console.error('Failed to auto-connect after authentication:', err);
      });
    } else if (!isAuthenticated && (connectionState.isConnected || connectionState.isConnecting)) {
      // Disconnect when authentication is lost
      connectionManager.disconnect();
    }
    
    return () => {
      connectionManager.off('state_change', handleStateChange);
      connectionManager.off('market_data', handleMarketData);
      connectionManager.off('orders', handleOrders);
      connectionManager.off('portfolio', handlePortfolio);
      connectionManager.off('recovery_attempt', handleRecoveryAttempt);
      connectionManager.off('recovery_success', handleRecoverySuccess);
      connectionManager.off('recovery_failed', handleRecoveryFailed);
      // Don't disconnect on unmount as this is a top-level provider
    };
  }, [connectionManager, isAuthenticated, connectionState.isConnected, connectionState.isConnecting]);
  
  // Add connection event listeners
  useEffect(() => {
    // WebSocket connection events
    const handleWSDisconnect = (data: any) => {
      toastService.error(`WebSocket Disconnected: ${data.reason}`, 7000);
    };

    const handleWSReconnecting = (data: any) => {
      toastService.warning(`Reconnecting WebSocket (Attempt ${data.attempt})...`, 5000);
    };

    // SSE connection events
    const handleSSEDisconnect = (data: any) => {
      toastService.error(`SSE Stream Disconnected: ${data.reason}`, 7000);
    };

    const handleSSEReconnecting = (data: any) => {
      toastService.warning(`Reconnecting SSE Stream (Attempt ${data.attempt})...`, 5000);
    };

    // Add listeners using proper methods instead of accessing private properties
    connectionManager.addWSEventListener('disconnected', handleWSDisconnect);
    connectionManager.addWSEventListener('reconnecting', handleWSReconnecting);
    connectionManager.addSSEEventListener('disconnected', handleSSEDisconnect);
    connectionManager.addSSEEventListener('reconnecting', handleSSEReconnecting);

    // Cleanup listeners
    return () => {
      connectionManager.removeWSEventListener('disconnected', handleWSDisconnect);
      connectionManager.removeWSEventListener('reconnecting', handleWSReconnecting);
      connectionManager.removeSSEEventListener('disconnected', handleSSEDisconnect);
      connectionManager.removeSSEEventListener('reconnecting', handleSSEReconnecting);
    };
  }, [connectionManager]);
  
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

  // Add function for manual reconnection
  const manualReconnect = useCallback(async () => {
    if (connectionManager.attemptRecovery) {
      return connectionManager.attemptRecovery('manual_user_request');
    } else {
      // Fallback to standard reconnect if attemptRecovery is not available
      return reconnect();
    }
  }, [connectionManager, reconnect]);
  
  const startSimulator = async (options: {
    initialSymbols?: string[],
    initialCash?: number
  } = {}) => {
    if (!isAuthenticated || !connectionState.isConnected) {
      console.warn('Cannot start simulator - user is not authenticated or not connected');
      return false;
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
  
  const streamMarketData = async (symbols: string[]) => {
    if (!isAuthenticated || !connectionState.isConnected) {
      console.warn('Cannot stream market data - user is not authenticated or not connected');
      return false;
    }
    return connectionManager.streamMarketData(symbols);
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
      marketData,
      orders,
      portfolio,
      streamMarketData,
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