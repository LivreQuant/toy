import { config } from '../../config';
import { EventEmitter } from '../../utils/event-emitter';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { CircuitBreaker, CircuitState } from '../../utils/circuit-breaker';
import { TokenManager } from '../auth/token-manager';
import { ConnectionStrategy } from './connection-strategy';
import { HeartbeatManager } from './heartbeat-manager';
import { WebSocketMessageHandler } from './message-handler';
import { MetricTracker } from './metric-tracker';
import { Logger } from '../../utils/logger';
import { 
  WebSocketOptions, 
  ConnectionMetrics, 
  DataSourceConfig, 
  ConnectionQuality,
  HeartbeatData 
} from './types';
import { 
  WebSocketError, 
  NetworkError, 
  AuthenticationError, 
  WebSocketErrorHandler 
} from './websocket-error';

export class WebSocketManager extends EventEmitter {
  private connectionStrategy: ConnectionStrategy;
  private heartbeatManager: HeartbeatManager | null = null;
  private messageHandler: WebSocketMessageHandler;
  private tokenManager: TokenManager;
  private metricTracker: MetricTracker;
  private errorHandler: WebSocketErrorHandler;
  private logger: Logger;
  
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
  private connectionQuality: ConnectionQuality = ConnectionQuality.DISCONNECTED;

  constructor(
    tokenManager: TokenManager, 
    options: WebSocketOptions = {},
    logger?: Logger
  ) {
    super();
    this.tokenManager = tokenManager;
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
  }

  private handleDisconnect(reason: string): void {
    if (reason !== 'user_disconnect') {
      this.attemptReconnect();
    }
  }

  private handleConnectionError(error: any): void {
    this.logger.error('WebSocket connection error:', error);
    this.attemptReconnect();
  }

  private handleComprehensiveError(error: any): void {
    if (error instanceof WebSocketError) {
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
      this.errorHandler.handleNetworkError(error, {
        tryAlternativeDataSource: this.tryAlternativeDataSource.bind(this),
        initiateOfflineMode: this.initiateOfflineMode.bind(this)
      });
    } else if (error instanceof AuthenticationError) {
      this.errorHandler.handleAuthenticationError(error, {
        tokenManager: this.tokenManager,
        manualReconnect: this.manualReconnect.bind(this),
        triggerLogout: this.triggerLogout.bind(this)
      });
    } else {
      this.errorHandler.handleUnknownError(error, {
        logger: this.logger,
        disconnect: this.disconnect.bind(this),
        attemptReconnect: this.attemptReconnect.bind(this)
      });
    }
  }

  private triggerLogout(): void {
    this.tokenManager.clearTokens();
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

      if (this.connectionQuality === ConnectionQuality.POOR) {
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
    }
  }

  private calculateConnectionQuality(): ConnectionQuality {
    const { latency, packetLoss } = this.connectionMetrics;

    if (latency < 50 && packetLoss < 1) return ConnectionQuality.EXCELLENT;
    if (latency < 100 && packetLoss < 3) return ConnectionQuality.GOOD;
    if (latency < 200 && packetLoss < 5) return ConnectionQuality.FAIR;
    if (latency >= 200 || packetLoss >= 5) return ConnectionQuality.POOR;

    return ConnectionQuality.DISCONNECTED;
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
    try {
      return this.circuitBreaker.execute(async () => {
        try {
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

          return true;
        } catch (connectionError: unknown) {
          const errorMessage = connectionError instanceof Error 
            ? connectionError.message 
            : 'Failed to establish WebSocket connection';
          
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
    this.emit('disconnected', reason);
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
    this.attemptReconnect();
  }
}