Let me continue with the refactored code:
typescriptCopy// src/services/connection/connection-manager.ts (continued)
      if (!wsConnected) {
        throw new Error('Failed to establish WebSocket connection');
      }
      
      // Connect to market data stream
      await this.marketDataStream.connect(response.sessionId);
      
      // Update state
      this.updateState({
        isConnected: true,
        isConnecting: false,
        sessionId: response.sessionId,
        simulatorId: response.simulatorId,
        simulatorStatus: response.simulatorStatus,
        error: null
      });
      
      // Store in session storage
      SessionStore.saveSession({
        sessionId: response.sessionId,
        simulatorId: response.simulatorId,
        reconnectAttempts: 0
      });
      
      return true;
    } catch (error) {
      console.error('Reconnection error:', error);
      this.updateState({ 
        isConnecting: false, 
        error: error instanceof Error ? error.message : 'Reconnection failed' 
      });
      return false;
    }
  }
  
  // Handle heartbeat data from websocket
  private handleHeartbeat(data: any): void {
    const now = Date.now();
    const latency = data.latency || (now - this.state.lastHeartbeatTime);
    
    this.updateState({
      lastHeartbeatTime: now,
      heartbeatLatency: latency,
      missedHeartbeats: 0
    });
    
    // Update connection quality based on latency
    let quality: ConnectionQuality = 'good';
    if (latency > 500) {
      quality = 'degraded';
    } else if (latency > 1000) {
      quality = 'poor';
    }
    
    this.updateState({ connectionQuality: quality });
    
    this.emit('heartbeat', {
      timestamp: now,
      latency
    });
  }
  
  // Start heartbeat for websocket connection
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatInterval = window.setInterval(() => {
      if (!this.state.isConnected) return;
      
      // Send heartbeat via WebSocket
      this.wsManager.send({ 
        type: 'heartbeat', 
        timestamp: Date.now() 
      });
    }, 15000); // Every 15 seconds
  }
  
  private stopHeartbeat(): void {
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
  
  // Start keep-alive for REST API connection
  private startKeepAlive(): void {
    this.stopKeepAlive();
    
    this.keepAliveInterval = window.setInterval(async () => {
      if (!this.state.isConnected || !this.state.sessionId) return;
      
      try {
        // Send keep-alive to server
        await this.sessionApi.keepAlive(this.state.sessionId);
        
        // Update session store
        SessionStore.updateActivity();
      } catch (error) {
        console.error('Keep-alive error:', error);
      }
    }, 30000); // Every 30 seconds
  }
  
  private stopKeepAlive(): void {
    if (this.keepAliveInterval !== null) {
      clearInterval(this.keepAliveInterval);
      this.keepAliveInterval = null;
    }
  }
  
  private updateState(updates: Partial<ConnectionState>): void {
    const prevState = { ...this.state };
    this.state = { ...this.state, ...updates };
    
    // Emit state change event
    this.emit('state_change', {
      previous: prevState,
      current: this.state
    });
  }
  
  // Get current connection state
  public getState(): ConnectionState {
    return { ...this.state };
  }
  
  // Stream market data for specific symbols
  public async streamMarketData(symbols: string[] = []): Promise<boolean> {
    if (!this.state.sessionId || !this.state.isConnected) {
      return false;
    }
    
    return this.marketDataStream.connect(this.state.sessionId, { symbols: symbols.join(',') });
  }
  
  // Control simulator
  public async startSimulator(): Promise<boolean> {
    if (!this.state.sessionId) {
      return false;
    }
    
    try {
      // This would call simulator start API
      this.updateState({ simulatorStatus: 'STARTING' });
      
      const response = await this.httpClient.post('/simulator/start', {
        sessionId: this.state.sessionId
      });
      
      if (response.success) {
        this.updateState({
          simulatorId: response.simulatorId,
          simulatorStatus: 'RUNNING'
        });
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Failed to start simulator:', error);
      return false;
    }
  }
  
  public async stopSimulator(): Promise<boolean> {
    if (!this.state.sessionId || !this.state.simulatorId) {
      return false;
    }
    
    try {
      this.updateState({ simulatorStatus: 'STOPPING' });
      
      const response = await this.httpClient.post('/simulator/stop', {
        sessionId: this.state.sessionId,
        simulatorId: this.state.simulatorId
      });
      
      if (response.success) {
        this.updateState({
          simulatorStatus: 'STOPPED',
          simulatorId: null
        });
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Failed to stop simulator:', error);
      return false;
    }
  }
  
  // Submit order
  public async submitOrder(order: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price?: number;
    type: 'MARKET' | 'LIMIT';
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
    const sessionId = this.state.sessionId;
    if (!sessionId) {
      return { success: false, error: 'No active session' };
    }
    
    try {
      const response = await this.ordersApi.submitOrder({
        sessionId,
        symbol: order.symbol,
        side: order.side,
        quantity: order.quantity,
        price: order.price,
        type: order.type,
        requestId: `order-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`
      });
      
      return { 
        success: response.success, 
        orderId: response.orderId,
        error: response.errorMessage
      };
    } catch (error) {
      console.error('Order submission error:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Order submission failed' 
      };
    }
  }
  
  // Cancel order
  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
    const sessionId = this.state.sessionId;
    if (!sessionId) {
      return { success: false, error: 'No active session' };
    }
    
    try {
      const response = await this.ordersApi.cancelOrder(sessionId, orderId);
      
      return { 
        success: response.success,
        error: response.success ? undefined : 'Failed to cancel order'
      };
    } catch (error) {
      console.error('Order cancellation error:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Order cancellation failed' 
      };
    }
  }
  
  // Get market data
  public getMarketData(): Record<string, MarketData> {
    return { ...this.marketData };
  }
  
  // Get orders
  public getOrders(): Record<string, OrderUpdate> {
    return { ...this.orders };
  }
  
  // Get portfolio
  public getPortfolio(): PortfolioUpdate | null {
    return this.portfolio ? { ...this.portfolio } : null;
  }
}
9. React Contexts:
Now let's implement the React contexts for our refactored code:
typescriptCopy// src/contexts/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { TokenManager } from '../services/auth/token-manager';
import { AuthApi } from '../api/auth';
import { HttpClient } from '../api/http-client';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => Promise<void>;
  error: string | null;
  tokenManager: TokenManager;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  // Create token manager
  const [tokenManager] = useState<TokenManager>(() => new TokenManager());
  
  // Create HTTP client
  const [httpClient] = useState<HttpClient>(() => new HttpClient('/api', tokenManager));
  
  // Create auth API client
  const [authApi] = useState<AuthApi>(() => new AuthApi(httpClient));
  
  // Set auth API in token manager for refresh
  useEffect(() => {
    tokenManager.setAuthApi(authApi);
  }, [tokenManager, authApi]);
  
  // Check if user is authenticated on mount
  useEffect(() => {
    const checkAuth = async () => {
      setIsLoading(true);
      
      try {
        const isAuth = tokenManager.isAuthenticated();
        setIsAuthenticated(isAuth);
        
        if (isAuth) {
          // Verify token is still valid by fetching a token
          const token = await tokenManager.getAccessToken();
          setIsAuthenticated(!!token);
        }
      } catch (err) {
        console.error('Authentication check failed:', err);
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };
    
    checkAuth();
  }, [tokenManager]);
  
  // Login function
  const login = async (username: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await authApi.login(username, password);
      
      // Store tokens
      tokenManager.storeTokens({
        accessToken: response.accessToken,
        refreshToken: response.refreshToken,
        expiresAt: Date.now() + (response.expiresIn * 1000)
      });
      
      setIsAuthenticated(true);
      return true;
    } catch (err) {
      console.error('Login failed:', err);
      setError(err instanceof Error ? err.message : 'Login failed');
      setIsAuthenticated(false);
      return false;
    } finally {
      setIsLoading(false);
    }
  };
  
  // Logout function
  const logout = async (): Promise<void> => {
    setIsLoading(true);
    
    try {
      await authApi.logout();
    } catch (err) {
      console.error('Logout failed:', err);
    } finally {
      // Always clear tokens regardless of API call success
      tokenManager.clearTokens();
      setIsAuthenticated(false);
      setIsLoading(false);
    }
  };
  
  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        login,
        logout,
        error,
        tokenManager
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// src/contexts/ConnectionContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { ConnectionManager, ConnectionState } from '../services/connection/connection-manager';
import { TokenManager } from '../services/auth/token-manager';
import { useAuth } from './AuthContext';

interface ConnectionContextType {
  connectionManager: ConnectionManager;
  connectionState: ConnectionState;
  connect: () => Promise<boolean>;
  disconnect: () => void;
  reconnect: () => Promise<boolean>;
  isConnected: boolean;
  isConnecting: boolean;
  connectionQuality: string;
  error: string | null;
  startSimulator: () => Promise<boolean>;
  stopSimulator: () => Promise<boolean>;
  submitOrder: (order: any) => Promise<any>;
  marketData: Record<string, any>;
  orders: Record<string, any>;
  portfolio: any;
  streamMarketData: (symbols: string[]) => Promise<boolean>;
}

const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

export const ConnectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { tokenManager, isAuthenticated } = useAuth();
  const [connectionManager] = useState<ConnectionManager>(() => 
    new ConnectionManager(
      '/api',                             // REST API endpoint
      `wss://${window.location.host}/ws`, // WebSocket endpoint
      '/api/stream/market-data',          // SSE endpoint
      tokenManager
    )
  );
  
  const [connectionState, setConnectionState] = useState<ConnectionState>(connectionManager.getState());
  const [marketData, setMarketData] = useState<Record<string, any>>({});
  const [orders, setOrders] = useState<Record<string, any>>({});
  const [portfolio, setPortfolio] = useState<any>(null);
  
  useEffect(() => {
    // Handle connection state changes
    const handleStateChange = ({ current }: { current: ConnectionState }) => {
      setConnectionState(current);
    };
    
    const handleMarketData = (data: any) => {
      setMarketData(data);
    };
    
    const handleOrders = (data: any) => {
      setOrders(data);
    };
    
    const handlePortfolio = (data: any) => {
      setPortfolio(data);
    };
    
    connectionManager.on('state_change', handleStateChange);
    connectionManager.on('market_data', handleMarketData);
    connectionManager.on('orders', handleOrders);
    connectionManager.on('portfolio', handlePortfolio);
    
    // Connect if authenticated
    if (isAuthenticated) {
      connectionManager.connect().catch(err => {
        console.error('Failed to connect on mount:', err);
      });
    }
    
    return () => {
      connectionManager.off('state_change', handleStateChange);
      connectionManager.off('market_data', handleMarketData);
      connectionManager.off('orders', handleOrders);
      connectionManager.off('portfolio', handlePortfolio);
      // Don't disconnect on unmount as this is a top-level provider
    };
  }, [connectionManager, isAuthenticated]);
  
  const connect = async () => {
    return connectionManager.connect();
  };
  
  const disconnect = () => {
    connectionManager.disconnect();
  };
  
  const reconnect = async () => {
    return connectionManager.reconnect();
  };

  const startSimulator = async () => {
    return connectionManager.startSimulator();
  };
  
  const stopSimulator = async () => {
    return connectionManager.stopSimulator();
  };
  
  const submitOrder = async (order: any) => {
    return connectionManager.submitOrder(order);
  };
  
  const streamMarketData = async (symbols: string[]) => {
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
      connectionQuality: connectionState.connectionQuality,
      error: connectionState.error,
      startSimulator,
      stopSimulator,
      submitOrder,
      marketData,
      orders,
      portfolio,
      streamMarketData
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
10. App Component and Routes:
typescriptCopy// src/App.tsx
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ConnectionProvider } from './contexts/ConnectionContext';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import SimulatorPage from './pages/SimulatorPage';
import ConnectionStatus from './components/Common/ConnectionStatus';
import ErrorBoundary from './components/Common/ErrorBoundary';
import LoadingScreen from './components/Common/LoadingScreen';
import { useAuth } from './contexts/AuthContext';
import { useConnection } from './contexts/ConnectionContext';

const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <ConnectionProvider>
          <AppRouter />
        </ConnectionProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
};

const AppRouter: React.FC = () => {
  const { isLoading } = useAuth();
  
  if (isLoading) {
    return <LoadingScreen message="Loading application..." />;
  }
  
  return (
    <Router>
      <div className="app-container">
        <div className="app-header">
          <ConnectionStatusWrapper />
        </div>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/home" element={<RequireAuth><HomePage /></RequireAuth>} />
          <Route path="/simulator" element={<RequireAuth><SimulatorPage /></RequireAuth>} />
          <Route path="/" element={<Navigate to="/home" replace />} />
        </Routes>
      </div>
    </Router>
  );
};

// Connection status with current state
const ConnectionStatusWrapper: React.FC = () => {
  const { isConnected, isConnecting, connectionQuality, connectionState } = useConnection();
  
  return (
    <ConnectionStatus 
      isConnected={isConnected}
      isConnecting={isConnecting}
      connectionQuality={connectionQuality}
      simulatorStatus={connectionState.simulatorStatus}
    />
  );
};

// Require authentication wrapper
const RequireAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  const { connect, isConnected, isConnecting } = useConnection();
  
  React.useEffect(() => {
    // Connect if authenticated and not already connected
    if (isAuthenticated && !isConnected && !isConnecting) {
      connect().catch(err => {
        console.error('Failed to connect in RequireAuth:', err);
      });
    }
  }, [isAuthenticated, isConnected, isConnecting, connect]);
  
  if (isLoading) {
    return <LoadingScreen message="Checking authentication..." />;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  // Even if authenticated, wait for connection (optional, depends on your UX approach)
  if (isConnecting) {
    return <LoadingScreen message="Establishing secure connection..." />;
  }
  
  return <>{children}</>;
};

export default App;
11. UI Components:
Here I've refactored the ConnectionStatus and Login components:
typescriptCopy// src/components/Common/ConnectionStatus.tsx
import React from 'react';
import './ConnectionStatus.css';

interface ConnectionStatusProps {
  isConnected: boolean;
  isConnecting: boolean;
  connectionQuality: string;
  simulatorStatus: string;
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({
  isConnected,
  isConnecting,
  connectionQuality,
  simulatorStatus
}) => {
  // Determine connection status
  let statusIcon = '❓';
  let statusClass = 'unknown';
  let statusText = 'Unknown';
  
  if (!isConnected && isConnecting) {
    statusIcon = '🔄';
    statusClass = 'connecting';
    statusText = 'Connecting...';
  } else if (!isConnected) {
    statusIcon = '❌';
    statusClass = 'disconnected';
    statusText = 'Disconnected';
  } else if (connectionQuality === 'good') {
    statusIcon = '✅';
    statusClass = 'good';
    statusText = 'Connected';
  } else if (connectionQuality === 'degraded') {
    statusIcon = '⚠️';
    statusClass = 'degraded';
    statusText = 'Connection Degraded';
  } else if (connectionQuality === 'poor') {
    statusIcon = '🔴';
    statusClass = 'poor';
    statusText = 'Connection Poor';
  }
  
  // Determine simulator status
  let simulatorStatusText = '';
  let simulatorStatusClass = '';
  
  switch (simulatorStatus) {
    case 'RUNNING':
      simulatorStatusText = 'Simulator Running';
      simulatorStatusClass = 'running';
      break;
    case 'STARTING':
      simulatorStatusText = 'Simulator Starting...';
      simulatorStatusClass = 'starting';
      break;
    case 'STOPPING':
      simulatorStatusText = 'Simulator Stopping...';
      simulatorStatusClass = 'stopping';
      break;
    case 'STOPPED':
      simulatorStatusText = 'Simulator Stopped';
      simulatorStatusClass = 'stopped';
      break;
    case 'ERROR':
      simulatorStatusText = 'Simulator Error';
      simulatorStatusClass = 'error';
      break;
    default:
      simulatorStatusText = 'Simulator Status Unknown';
      simulatorStatusClass = 'unknown';
  }
  
  return (
    <div className={`connection-indicator ${statusClass}`}>
      <div className="indicator-icon">{statusIcon}</div>
      <div className="indicator-text">
        <div className="status-text">{statusText}</div>
        {simulatorStatus && (
          <div className={`simulator-status ${simulatorStatusClass}`}>
            {simulatorStatusText}
          </div>
        )}
      </div>
    </div>
  );
};

export default ConnectionStatus;