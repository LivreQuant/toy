// src/services/websocket/websocket-manager.ts
import { config } from '../../config';
import { EventEmitter } from '../../utils/event-emitter';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { CircuitBreaker, CircuitState } from '../../utils/circuit-breaker';
import { TokenManager } from '../auth/token-manager';
import { ConnectionStrategy } from './connection-strategy';
import { HeartbeatManager } from './heartbeat-manager';
import { ErrorHandler, ErrorSeverity } from '../../utils/error-handler';
import { WebSocketMessageHandler } from './message-handler';
import { DeviceIdManager } from '../../utils/device-id-manager';
import { MetricTracker } from './metric-tracker';
import { Logger } from '../../utils/logger';
import { 
  WebSocketOptions, 
  ConnectionMetrics, 
  DataSourceConfig, 
  ConnectionQuality as WSConnectionQuality,
  HeartbeatData 
} from './types';
import { 
  WebSocketError, 
  NetworkError, 
  AuthenticationError, 
  WebSocketErrorHandler 
} from './websocket-error';
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus,
  ConnectionQuality
} from '../connection/unified-connection-state';

export class WebSocketManager extends EventEmitter {
  private connectionStrategy: ConnectionStrategy;
  private heartbeatManager: HeartbeatManager | null = null;
  private messageHandler: WebSocketMessageHandler;
  private tokenManager: TokenManager;
  private metricTracker: MetricTracker;
  private errorHandler: WebSocketErrorHandler;
  private logger: Logger;
  private unifiedState: UnifiedConnectionState;
  
  private backoffStrategy: BackoffStrategy;
  private circuitBreaker: CircuitBreaker;
  private reconnectTimer: number | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;

  private connectionMetrics: ConnectionMetrics = {
    latency: 0,
    bandwidth: 0,
    packetLoss: 0
  };
  
  private dataSources: DataSourceConfig[] = [
    {
      type: 'websocket',
      url: config.wsBaseUrl,
      priority: 1
    },
    {
      type: 'sse',
      url: config.sseBaseUrl,
      priority: 2
    },
    {
      type: 'rest',
      url: config.apiBaseUrl,
      priority: 3
    }
  ];

  private currentDataSource: DataSourceConfig;
  private connectionQuality: WSConnectionQuality = WSConnectionQuality.DISCONNECTED;

  constructor(
    tokenManager: TokenManager, 
    unifiedState: UnifiedConnectionState,
    options: WebSocketOptions = {},
    logger?: Logger
  ) {
    super();
    this.tokenManager = tokenManager;
    this.unifiedState = unifiedState;
    this.logger = logger || new Logger('WebSocketManager');
    this.metricTracker = new MetricTracker(this.logger);
    this.errorHandler = new WebSocketErrorHandler(this.logger);
    
    this.backoffStrategy = new BackoffStrategy(1000, 30000);
    this.circuitBreaker = new CircuitBreaker('websocket', 5, 60000);
    this.currentDataSource = this.dataSources[0];

    this.connectionStrategy = new ConnectionStrategy({
      tokenManager,
      eventEmitter: this,
      options
    });

    this.messageHandler = new WebSocketMessageHandler(this);

    this.setupErrorHandling();
    this.setupReconnectionListeners();
    this.monitorConnection();
  }

  private setupErrorHandling(): void {
    this.on('error', this.handleComprehensiveError.bind(this));
  }

  private setupReconnectionListeners(): void {
    this.on('disconnected', this.handleDisconnect.bind(this));
    this.on('error', this.handleConnectionError.bind(this));
    
    // Forward heartbeat events to unified state
    this.on('heartbeat', this.handleHeartbeatWithUnifiedState.bind(this));
  }

  private handleHeartbeatWithUnifiedState(data: any): void {
    // Update the unified state with heartbeat data
    this.unifiedState.updateHeartbeat(
      data.timestamp || Date.now(), 
      data.latency || 0
    );
    
    // If simulator status is included in heartbeat, update it
    if (data.simulatorStatus) {
      this.unifiedState.updateSimulatorStatus(data.simulatorStatus);
    }
  }

  private handleDisconnect(reason: string): void {
    // Update unified state
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
      status: ConnectionStatus.DISCONNECTED,
      error: reason
    });
    
    if (reason !== 'user_disconnect') {
      this.attemptReconnect();
    }
  }

  private handleConnectionError(error: any): void {
    this.logger.error('WebSocket connection error:', error);
    
    // Update unified state
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
      error: error instanceof Error ? error.message : 'Connection error'
    });
    
    // Use standardized error handler
    ErrorHandler.handleConnectionError(
      error instanceof Error ? error : 'Connection lost',
      ErrorSeverity.MEDIUM,
      'WebSocket'
    );
    
    this.attemptReconnect();
  }

  private getErrorSeverity(errorCode: string): ErrorSeverity {
    switch (errorCode) {
      case 'UNAUTHORIZED':
        return ErrorSeverity.HIGH;
      case 'CONNECTION_FAILED':
        return ErrorSeverity.MEDIUM;
      case 'PROTOCOL_ERROR':
        return ErrorSeverity.HIGH;
      default:
        return ErrorSeverity.MEDIUM;
    }
  }

  private handleComprehensiveError(error: any): void {
    if (error instanceof WebSocketError) {
      const severity = this.getErrorSeverity(error.code);
      ErrorHandler.handleConnectionError(error, severity, 'WebSocket');

      // Update unified state with error
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        error: `${error.code}: ${error.message}`
      });

      this.errorHandler.handleWebSocketError(error, {
        reconnectAttempts: this.reconnectAttempts,
        circuitBreaker: this.circuitBreaker,
        tokenManager: this.tokenManager,
        disconnect: this.disconnect.bind(this),
        attemptReconnect: this.attemptReconnect.bind(this),
        triggerLogout: this.triggerLogout.bind(this),
        manualReconnect: this.manualReconnect.bind(this)
      });
    } else if (error instanceof NetworkError) {
      ErrorHandler.handleConnectionError(error, ErrorSeverity.MEDIUM, 'Network');

      // Update unified state with network error
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        error: `Network error: ${error.type} - ${error.message}`
      });

      this.errorHandler.handleNetworkError(error, {
        tryAlternativeDataSource: this.tryAlternativeDataSource.bind(this),
        initiateOfflineMode: this.initiateOfflineMode.bind(this)
      });
    } else if (error instanceof AuthenticationError) {
      ErrorHandler.handleAuthError(error, ErrorSeverity.HIGH);

      // Update unified state with auth error
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        error: `Authentication error: ${error.message}`
      });

      this.errorHandler.handleAuthenticationError(error, {
        tokenManager: this.tokenManager,
        manualReconnect: this.manualReconnect.bind(this),
        triggerLogout: this.triggerLogout.bind(this)
      });
    } else {
      ErrorHandler.handleConnectionError(
        error instanceof Error ? error : 'Unknown error',
        ErrorSeverity.HIGH,
        'WebSocket'
      );

      // Update unified state with unknown error
      this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  }

  private triggerLogout(): void {
    this.tokenManager.clearTokens();
    ErrorHandler.handleAuthError('Session expired. Please log in again.', ErrorSeverity.HIGH);
    this.emit('force_logout', 'Authentication failed');
    this.logger.error('User logged out due to authentication failure');
  }

  private initiateOfflineMode(): void {
    this.emit('offline_mode_activated');
    this.logger.warn('Switching to offline mode');
  }

  public checkSessionReady(sessionId: string): Promise<boolean> {
    return new Promise((resolve, reject) => {
      const message = {
        type: 'check_session_ready',
        sessionId: sessionId
      };

      const responseHandler = (response: any) => {
        if (response.type === 'session_ready_response' && response.sessionId === sessionId) {
          resolve(response.ready);
          this.messageHandler.off('message', responseHandler);
        }
      };

      this.messageHandler.on('message', responseHandler);
      this.send(message);

      setTimeout(() => {
        this.messageHandler.off('message', responseHandler);
        reject(new Error('Session readiness check timed out'));
      }, 5000);
    });
  }

  private async monitorConnection(): Promise<void> {
    setInterval(async () => {
      const metrics = await this.metricTracker.collectMetrics(
        this.connectionStrategy.getWebSocket() || undefined
      );
      this.updateConnectionMetrics(metrics);

      if (this.connectionQuality === WSConnectionQuality.POOR) {
        await this.tryAlternativeDataSource();
      }
    }, 30000);
  }

  private updateConnectionMetrics(newMetrics: Partial<ConnectionMetrics>): void {
    this.connectionMetrics = {
      ...this.connectionMetrics,
      ...newMetrics
    };

    const newQuality = this.calculateConnectionQuality();
    if (newQuality !== this.connectionQuality) {
      this.connectionQuality = newQuality;
      this.emit('connection_quality_changed', this.connectionQuality);
      
      // Map WS quality to unified quality
      let unifiedQuality: ConnectionQuality;
      switch (newQuality) {
        case WSConnectionQuality.EXCELLENT:
        case WSConnectionQuality.GOOD:
          unifiedQuality = ConnectionQuality.GOOD;
          break;
        case WSConnectionQuality.FAIR:
          unifiedQuality = ConnectionQuality.DEGRADED;
          break;
        case WSConnectionQuality.POOR:
        case WSConnectionQuality.DISCONNECTED:
          unifiedQuality = ConnectionQuality.POOR;
          break;
        default:
          unifiedQuality = ConnectionQuality.GOOD;
      }
      
      // Update latency in unified state
      if (this.connectionMetrics.latency) {
        this.unifiedState.updateHeartbeat(Date.now(), this.connectionMetrics.latency);
      }
    }
  }

  private calculateConnectionQuality(): WSConnectionQuality {
    const { latency, packetLoss } = this.connectionMetrics;

    if (latency < 50 && packetLoss < 1) return WSConnectionQuality.EXCELLENT;
    if (latency < 100 && packetLoss < 3) return WSConnectionQuality.GOOD;
    if (latency < 200 && packetLoss < 5) return WSConnectionQuality.FAIR;
    if (latency >= 200 || packetLoss >= 5) return WSConnectionQuality.POOR;

    return WSConnectionQuality.DISCONNECTED;
  }

  private async tryAlternativeDataSource(): Promise<boolean> {
    const alternativeSources = this.dataSources
      .filter(source => source !== this.currentDataSource)
      .sort((a, b) => a.priority - b.priority);

    for (const source of alternativeSources) {
      try {
        switch (source.type) {
          case 'websocket':
            return await this.connectWebSocket(source);
          case 'sse':
            return await this.connectSSE(source);
          case 'rest':
            return await this.connectREST(source);
        }
      } catch (error) {
        this.logger.warn(`Failed to connect to ${source.type} source:`, error);
        continue;
      }
    }

    return false;
  }

  private async connectWebSocket(source: DataSourceConfig): Promise<boolean> {
    const connected = await this.connect();
    if (connected) {
      this.currentDataSource = source;
      return true;
    }
    return false;
  }

  private async connectSSE(source: DataSourceConfig): Promise<boolean> {
    try {
      const eventSource = new EventSource(source.url);
      
      return new Promise((resolve) => {
        eventSource.onopen = () => {
          this.currentDataSource = source;
          resolve(true);
        };
        
        eventSource.onerror = () => resolve(false);
      });
    } catch (error) {
      return false;
    }
  }

  private async connectREST(source: DataSourceConfig): Promise<boolean> {
    try {
      const response = await fetch(source.url, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${await this.tokenManager.getAccessToken()}`
        }
      });
      
      return response.ok;
    } catch (error) {
      return false;
    }
  }

  public async connect(): Promise<boolean> {
    // Update unified state to connecting
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
      status: ConnectionStatus.CONNECTING,
      error: null
    });
    
    try {
      return this.circuitBreaker.execute(async () => {
        try {
          // Generate device ID on connection if it doesn't exist
          if (!DeviceIdManager.hasDeviceId()) {
            DeviceIdManager.getDeviceId(); // Creates and stores a new one
          }
          
          const ws = await this.connectionStrategy.connect();

          ws.onmessage = (event) => this.messageHandler.handleMessage(event);
          ws.onerror = (error) => {
            throw new WebSocketError('Connection error', 'CONNECTION_FAILED');
          };

          this.heartbeatManager = new HeartbeatManager({
            ws,
            eventEmitter: this
          });
          this.heartbeatManager.start();

          if (this.reconnectTimer !== null) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
          }
          
          // Update unified state to connected
          this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
            status: ConnectionStatus.CONNECTED,
            lastConnected: Date.now(),
            error: null
          });

          return true;
        } catch (connectionError: unknown) {
          const errorMessage = connectionError instanceof Error 
            ? connectionError.message 
            : 'Failed to establish WebSocket connection';
          
          // Update unified state with error
          this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
            status: ConnectionStatus.DISCONNECTED,
            error: errorMessage
          });
          
          throw new WebSocketError(
            errorMessage, 
            'CONNECTION_FAILED'
          );
        }
      });
    } catch (error) {
      this.emit('error', error);
      return false;
    }
  }

  public send(message: any): void {
    const ws = this.connectionStrategy.getWebSocket();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    } else {
      throw new Error('WebSocket is not open');
    }
  }

  public disconnect(reason: string = 'user_disconnect'): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    this.heartbeatManager?.stop();
    this.connectionStrategy.disconnect();
    
    // Update unified state
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
      status: ConnectionStatus.DISCONNECTED,
      error: reason
    });
    
    this.emit('disconnected', reason);
  }

  public dispose(): void {
    this.disconnect('manager_disposed');
    
    // Clean up all event listeners
    super.dispose();
    
    // Clear any other resources
    if (this.metricTracker instanceof Disposable) {
      this.metricTracker.dispose();
    }
  }
  
  public terminateConnection(reason: string = 'session_terminated'): void {
    this.disconnect(reason);
    DeviceIdManager.clearDeviceId();
  }
  
  private attemptReconnect(): void {
    if (this.reconnectTimer !== null) return;

    if (this.circuitBreaker.getState() === CircuitState.OPEN) {
      this.logger.warn('Circuit breaker is open. Preventing reconnection.');
      return;
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.circuitBreaker.reset();
      this.reconnectAttempts = 0;
    }

    this.reconnectAttempts++;
    
    // Update unified state with recovery attempt
    this.unifiedState.updateRecovery(true, this.reconnectAttempts);

    const delay = this.backoffStrategy.nextBackoffTime();

    this.emit('reconnecting', {
      attempt: this.reconnectAttempts,
      delay
    });

    this.reconnectTimer = window.setTimeout(async () => {
      try {
        const connected = await this.connect();
        
        if (connected) {
          this.reconnectAttempts = 0;
          this.backoffStrategy.reset();
          this.reconnectTimer = null;
          
          // Update unified state for successful recovery
          this.unifiedState.updateRecovery(false, 0);
        } else {
          this.attemptReconnect();
        }
      } catch (error) {
        this.logger.error('Reconnection failed:', error);
        this.attemptReconnect();
      }
    }, delay);
  }

  public manualReconnect(): void {
    this.reconnectAttempts = 0;
    this.backoffStrategy.reset();
    this.circuitBreaker.reset();
    
    // Update unified state
    this.unifiedState.updateRecovery(true, 1);
    
    this.attemptReconnect();
  }
  
  public getConnectionHealth() {
    // Return a structure that maps to the unified state format
    return {
      status: this.connectionStrategy.getWebSocket()?.readyState === WebSocket.OPEN 
        ? 'connected' 
        : this.isConnecting() ? 'connecting' : 'disconnected',
      quality: this.connectionQuality,
      error: this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).error
    };
  }
  
  public isConnecting(): boolean {
    return this.reconnectTimer !== null || 
           this.connectionStrategy.getWebSocket()?.readyState === WebSocket.CONNECTING;
  }
}