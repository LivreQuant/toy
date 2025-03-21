// src/contexts/ConnectionContext.tsx
import React, { createContext, useContext, useEffect, useState, useMemo } from 'react';
import { EnhancedConnectionManager, ConnectionState, ConnectionEvent } from '../services/connections/EnhancedConnectionManager';
import { SessionStore } from '../services/session/SessionStore';
import { SimulatorStatus } from '../types/simulator';

interface ConnectionContextState {
  isConnected: boolean;
  isConnecting: boolean;
  hasSession: boolean;
  sessionId: string | null;
  simulatorId: string | null;
  simulatorStatus: SimulatorStatus;
  connectionQuality: 'good' | 'degraded' | 'poor';
  reconnectAttempt: number;
  maxReconnectAttempts: number;
  lastHeartbeatTime: number;
  heartbeatLatency: number | null;
  error: string | null;
  connect: (token: string) => Promise<boolean>;
  reconnect: () => Promise<boolean>;
  disconnect: () => void;
  canSubmitOrders: boolean;
  reconnectWithBackoff: () => Promise<boolean>;
  updateConnectionQuality: () => Promise<void>;
}

const ConnectionContext = createContext<ConnectionContextState | undefined>(undefined);

export const ConnectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [hasSession, setHasSession] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [simulatorId, setSimulatorId] = useState<string | null>(null);
  const [simulatorStatus, setSimulatorStatus] = useState<SimulatorStatus>('UNKNOWN');
  const [connectionQuality, setConnectionQuality] = useState<'good' | 'degraded' | 'poor'>('poor');
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [maxReconnectAttempts] = useState(10);
  const [lastHeartbeatTime, setLastHeartbeatTime] = useState(0);
  const [heartbeatLatency, setHeartbeatLatency] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Initialize connection manager
  const connectionManager = useMemo(() => new EnhancedConnectionManager(), []);
  
  // Determine if order submission should be allowed
  const canSubmitOrders = useMemo(() => {
    // Can only submit orders when:
    // 1. Connected
    // 2. Not reconnecting
    // 3. Simulator is running
    // 4. Connection quality is not poor
    // 5. Heartbeat received in last 10 seconds
    const connectionOk = isConnected && !isConnecting;
    const simulatorOk = simulatorStatus === 'RUNNING';
    const qualityOk = connectionQuality !== 'poor';
    const heartbeatOk = Date.now() - lastHeartbeatTime < 10000; // 10 seconds
    
    return connectionOk && simulatorOk && qualityOk && heartbeatOk;
  }, [isConnected, isConnecting, simulatorStatus, connectionQuality, lastHeartbeatTime]);
  
  useEffect(() => {
    // Set up event listeners
    const handleStateChange = (data: any) => {
      setIsConnecting(data.newState === ConnectionState.CONNECTING || 
                     data.newState === ConnectionState.RECONNECTING);
      setIsConnected(data.newState === ConnectionState.CONNECTED);
      
      if (data.newState === ConnectionState.FAILED) {
        setError('Connection failed. Please try again later.');
      }
    };
    
    const handleSession = (data: any) => {
      if (data.valid) {
        setHasSession(true);
        setSessionId(data.sessionId);
        setError(null);
      } else {
        setHasSession(false);
        
        if (data.reason === 'max_attempts_reached') {
          setError('Failed to reconnect after multiple attempts. Please reload the page.');
        } else if (data.reason === 'create_failed') {
          setError(data.error || 'Failed to create session');
        } else if (data.reason === 'network_error') {
          setError('Network connection error. Please check your connection.');
        }
      }
    };
    
    const handleReconnecting = (data: any) => {
      setReconnectAttempt(data.attempt);
    };
    
    const handleSimulator = (data: any) => {
      if (data.id) {
        setSimulatorId(data.id);
      }
      
      if (data.status) {
        setSimulatorStatus(data.status);
      }
      
      if (data.error) {
        console.error('Simulator error:', data.error);
      }
    };
    
    const handleHeartbeat = (data: any) => {
      if (data.success) {
        setLastHeartbeatTime(data.timestamp);
        setHeartbeatLatency(data.latency);
      }
    };
    
    const handleAllEvents = (event: ConnectionEvent) => {
      // Update connection quality after any event
      setConnectionQuality(connectionManager.getConnectionQuality());
    };
    
    connectionManager.on('state_change', handleStateChange);
    connectionManager.on('session', handleSession);
    connectionManager.on('reconnecting', handleReconnecting);
    connectionManager.on('simulator', handleSimulator);
    connectionManager.on('heartbeat', handleHeartbeat);
    connectionManager.on('all', handleAllEvents);
    
    // Check for existing session
    const existingSession = SessionStore.getSession();
    if (existingSession && existingSession.token && existingSession.sessionId) {
      setIsConnecting(true);
      
      // Try to reconnect with stored session
      connectionManager.reconnect(
        existingSession.token, 
        existingSession.sessionId, 
        existingSession.simulatorId
      ).then(success => {
        if (success) {
          setSimulatorId(existingSession.simulatorId || null);
        }
      });
    }
    
    // Clean up on unmount
    return () => {
      connectionManager.off('state_change', handleStateChange);
      connectionManager.off('session', handleSession);
      connectionManager.off('reconnecting', handleReconnecting);
      connectionManager.off('simulator', handleSimulator);
      connectionManager.off('heartbeat', handleHeartbeat);
      connectionManager.off('all', handleAllEvents);
    };
  }, [connectionManager]);
  
  const connect = async (token: string): Promise<boolean> => {
    setIsConnecting(true);
    setError(null);
    return connectionManager.connect(token);
  };
  
  const reconnect = async (): Promise<boolean> => {
    const session = SessionStore.getSession();
    if (!session || !session.token || !session.sessionId) {
      setError('No session data available for reconnection');
      return false;
    }
    
    setIsConnecting(true);
    setError(null);
    return connectionManager.reconnect(
      session.token, 
      session.sessionId, 
      session.simulatorId
    );
  };
  
  const disconnect = () => {
    connectionManager.disconnect();
    setIsConnected(false);
    setHasSession(false);
    setSessionId(null);
    setSimulatorId(null);
    setSimulatorStatus('UNKNOWN');
    setError(null);
  };
  
  return (
    <ConnectionContext.Provider
      value={{
        isConnected,
        isConnecting,
        hasSession,
        sessionId,
        simulatorId,
        simulatorStatus,
        connectionQuality,
        reconnectAttempt,
        maxReconnectAttempts,
        lastHeartbeatTime,
        heartbeatLatency,
        error,
        connect,
        reconnect,
        disconnect,
        canSubmitOrders,
        reconnectWithBackoff: connectionManager.reconnectWithBackoff.bind(connectionManager),
        updateConnectionQuality: connectionManager.updateConnectionQuality.bind(connectionManager),
      }}
    >
      {children}
    </ConnectionContext.Provider>
  );
};

export const useConnection = (): ConnectionContextState => {
  const context = useContext(ConnectionContext);
  if (context === undefined) {
    throw new Error('useConnection must be used within a ConnectionProvider');
  }
  return context;
};