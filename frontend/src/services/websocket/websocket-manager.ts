import { config } from '../../config';
import { EventEmitter } from '../../utils/event-emitter';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { CircuitBreaker, CircuitState } from '../../utils/circuit-breaker';
import { TokenManager } from '../auth/token-manager';
import { ConnectionStrategy } from './connection-strategy';
import { HeartbeatManager } from './heartbeat-manager';
import { WebSocketMessageHandler } from './message-handler';
import { MetricTracker } from './metric-tracker';
import { 
  WebSocketOptions, 
  ConnectionMetrics, 
  DataSourceConfig, 
  ConnectionQuality,
  HeartbeatData 
} from './types';

export class WebSocketManager extends EventEmitter {
  private connectionStrategy: ConnectionStrategy;
  private heartbeatManager: HeartbeatManager | null = null;
  private messageHandler: WebSocketMessageHandler;
  private tokenManager: TokenManager;
  private metricTracker: MetricTracker;
  
  // Connection management
  private backoffStrategy: BackoffStrategy;
  private circuitBreaker: CircuitBreaker;
  private reconnectTimer: number | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;

  // Connection metrics and sources
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
    options: WebSocketOptions = {}
  ) {
    super();
    this.tokenManager = tokenManager;
    this.metricTracker = new MetricTracker();
    
    this.backoffStrategy = new BackoffStrategy(1000, 30000);
    this.circuitBreaker = new CircuitBreaker('websocket', 5, 60000);
    this.currentDataSource = this.dataSources[0];

    this.connectionStrategy = new ConnectionStrategy({
      tokenManager,
      eventEmitter: this,
      options
    });

    this.messageHandler = new WebSocketMessageHandler(this);

    this.setupReconnectionListeners();
    this.monitorConnection();
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
    console.error('WebSocket connection error:', error);
    this.attemptReconnect();
  }

  private attemptReconnect(): void {
    if (this.reconnectTimer !== null) return;

    if (this.circuitBreaker.getState() === CircuitState.OPEN) {
      console.warn('Circuit breaker is open. Preventing reconnection.');
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
        console.error('Reconnection failed:', error);
        this.attemptReconnect();
      }
    }, delay);
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
        console.warn(`Failed to connect to ${source.type} source:`, error);
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

  // Add method to check session readiness via WebSocket
  public checkSessionReady(sessionId: string): Promise<boolean> {
    return new Promise((resolve, reject) => {
      // Create a message to request session readiness
      const message = {
        type: 'check_session_ready',
        sessionId: sessionId
      };

      // Use message handler to track response
      const responseHandler = (response: any) => {
        if (response.type === 'session_ready_response' && response.sessionId === sessionId) {
          resolve(response.ready);
          this.messageHandler.off('message', responseHandler);
        }
      };

      // Add temporary listener for session ready response
      this.messageHandler.on('message', responseHandler);

      // Send check request
      this.send(message);

      // Set timeout for the check
      setTimeout(() => {
        this.messageHandler.off('message', responseHandler);
        reject(new Error('Session readiness check timed out'));
      }, 5000);
    });
  }

  private monitorConnection(): void {
    setInterval(async () => {
      const metrics = await this.metricTracker.collectMetrics();
      this.updateConnectionMetrics(metrics);

      if (this.connectionQuality === ConnectionQuality.POOR) {
        await this.tryAlternativeDataSource();
      }
    }, 30000);
  }

  public async connect(): Promise<boolean> {
    try {
      return this.circuitBreaker.execute(async () => {
        const ws = await this.connectionStrategy.connect();

        ws.onmessage = (event) => this.messageHandler.handleMessage(event);

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
      });
    } catch (error) {
      this.emit('error', error);
      return false;
    }
  }

  // Ensure send method exists
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

  public manualReconnect(): void {
    this.reconnectAttempts = 0;
    this.backoffStrategy.reset();
    this.circuitBreaker.reset();
    this.attemptReconnect();
  }
}