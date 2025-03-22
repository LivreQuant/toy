// src/contexts/ConnectionContext.tsx
import React, { createContext, useContext, useEffect, useState, useMemo } from 'react';
import { EnhancedConnectionManager } from '../services/connections/EnhancedConnectionManager';
import { ConnectionState } from '../services/connections/ConnectionTypes';
import { SessionStore } from '../services/session/SessionStore';
import { getServiceConfig } from '../services/config/ServiceConfig';
import { TokenManager } from '../services/auth/TokenManager';

// Define simulator status type if not already defined elsewhere
export type SimulatorStatus = 'UNKNOWN' | 'STARTING' | 'RUNNING' | 'STOPPING' | 'STOPPED' | 'ERROR';

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
  // src/contexts/ConnectionContext.tsx (continued)
  podName: string | null;
  podSwitched: boolean;
  connect: (token: string) => Promise<boolean>;
  reconnect: () => Promise<boolean>;
  disconnect: () => void;
  canSubmitOrders: boolean;
  reconnectWithBackoff: () => Promise<boolean>;
  updateConnectionQuality: () => Promise<void>;
  tokenManager: TokenManager;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
}

const ConnectionContext = createContext<ConnectionContextState | undefined>(undefined);

export const ConnectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Basic connection states
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [hasSession, setHasSession] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [simulatorId, setSimulatorId] = useState<string | null>(null);
  const [simulatorStatus, setSimulatorStatus] = useState<SimulatorStatus>('UNKNOWN');
  
  // Connection quality metrics
  const [connectionQuality, setConnectionQuality] = useState<'good' | 'degraded' | 'poor'>('good');
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [maxReconnectAttempts, setMaxReconnectAttempts] = useState(15); // Increased for EKS
  const [lastHeartbeatTime, setLastHeartbeatTime] = useState(0);
  const [heartbeatLatency, setHeartbeatLatency] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // EKS-specific tracking
  const [podName, setPodName] = useState<string | null>(null);
  const [podSwitched, setPodSwitched] = useState(false);
  
  // Get service configuration
  const serviceConfig = useMemo(() => getServiceConfig(), []);
  
  // Initialize token manager
  const tokenManager = useMemo(() => new TokenManager(), []);
  
  // Initialize connection manager
  const connectionManager = useMemo(() => new EnhancedConnectionManager(tokenManager), [tokenManager]);
  
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
    // Update maxReconnectAttempts from config
    setMaxReconnectAttempts(serviceConfig.maxReconnectAttempts || 15);
    
    // Register token refresh handler
    tokenManager.onTokenRefresh(() => {
      // If we're connected, update the token in the connection manager
      if (isConnected) {
        const tokens = tokenManager.getTokens();
        if (tokens) {
          connectionManager.updateAuthToken(tokens.accessToken);
        }
      }
    });
    
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
        
        // Handle pod info if present
        if (data.podName) {
          const oldPod = podName;
          setPodName(data.podName);
          
          if (oldPod && oldPod !== data.podName) {
            console.log(`Pod switched from ${oldPod} to ${data.podName}`);
            setPodSwitched(true);
          }
        }
      } else {
        setHasSession(false);
        
        if (data.reason === 'max_attempts_reached') {
          setError('Failed to reconnect after multiple attempts. Please reload the page.');
        } else if (data.reason === 'create_failed') {
          setError(data.error || 'Failed to create session');
        } else if (data.reason === 'network_error') {
          setError('Network connection error. Please check your connection.');
        } else if (data.reason === 'no_token') {
          setError('Authentication token expired. Please log in again.');
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
        setSimulatorStatus(data.status as SimulatorStatus);
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
    
    const handleConnectionQuality = (data: any) => {
      setConnectionQuality(data.quality);
    };
    
    const handlePodSwitched = (data: any) => {
      console.log(`Pod switched from ${data.oldPod} to ${data.newPod}`);
      setPodName(data.newPod);
      setPodSwitched(true);
    };
    
    // Register all event handlers
    connectionManager.on('state_change', handleStateChange);
    connectionManager.on('session', handleSession);
    connectionManager.on('reconnecting', handleReconnecting);
    connectionManager.on('simulator', handleSimulator);
    connectionManager.on('heartbeat', handleHeartbeat);
    connectionManager.on('connection_quality', handleConnectionQuality);
    connectionManager.on('pod_switched', handlePodSwitched);
    
    // Check for existing session and token
    const tokens = tokenManager.getTokens();
    if (tokens && tokenManager.isAuthenticated()) {
      // We have a valid token, check for existing session
      setIsConnecting(true);
      
      tokenManager.getAccessToken().then(token => {
        if (token) {
          // Try to reconnect with stored session
          const existingSession = SessionStore.getSession();
          if (existingSession && existingSession.sessionId) {
            connectionManager.reconnect(
              token, 
              existingSession.sessionId, 
              existingSession.simulatorId
            ).then(success => {
              if (success) {
                setSimulatorId(existingSession.simulatorId || null);
                setPodName(existingSession.connectionInfo?.currentPodName || null);
                setPodSwitched(SessionStore.hasPodSwitched());
              }
            });
          } else {
            // No existing session but we have a token - create new session
            connectionManager.connect(token);
          }
        } else {
          setIsConnecting(false);
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
      connectionManager.off('connection_quality', handleConnectionQuality);
      connectionManager.off('pod_switched', handlePodSwitched);
    };
  }, [connectionManager, podName, serviceConfig.maxReconnectAttempts, tokenManager, isConnected]);
  
  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      setIsConnecting(true);
      setError(null);
      
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || errorData.error_message || 'Login failed');
      }
      
      const data = await response.json();
      
      // Store tokens - ensure consistent naming
      tokenManager.storeTokens({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        expiresAt: Date.now() + (data.expires_in * 1000),
      });
      
      // Connect with the new token
      return connectionManager.connect(data.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
      setIsConnecting(false);
      return false;
    }
  };
  
  const logout = () => {
    const tokens = tokenManager.getTokens();
    if (tokens) {
      // Call logout API
      fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${tokens.accessToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: tokens.refreshToken }),
      }).catch(err => {
        console.error('Logout error:', err);
      });
    }
    
    // Disconnect and clear tokens
    connectionManager.disconnect();
    tokenManager.clearTokens();
    SessionStore.clearSession();
    
    // Reset states
    setSessionId(null);
    setSimulatorId(null);
    setSimulatorStatus('UNKNOWN');
    setPodName(null);
    setPodSwitched(false);
    setHasSession(false);
  };
  
  // API methods
  const connect = async (token: string): Promise<boolean> => {
    setIsConnecting(true);
    setError(null);
    return connectionManager.connect(token);
  };
  
  const reconnect = async (): Promise<boolean> => {
    const token = await tokenManager.getAccessToken();
    if (!token) {
      setError('Authentication token expired. Please log in again.');
      return false;
    }
    
    const session = SessionStore.getSession();
    if (!session || !session.sessionId) {
      setError('No session data available for reconnection');
      return false;
    }
    
    setIsConnecting(true);
    setError(null);
    return connectionManager.reconnect(
      token, 
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
    setPodName(null);
    setPodSwitched(false);
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
        podName,
        podSwitched,
        connect,
        reconnect,
        disconnect,
        canSubmitOrders,
        reconnectWithBackoff: connectionManager.reconnectWithBackoff.bind(connectionManager),
        updateConnectionQuality: connectionManager.updateConnectionQuality.bind(connectionManager),
        tokenManager,
        login,
        logout,
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