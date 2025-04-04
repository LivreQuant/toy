// src/services/connection/connection-lifecycle.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { SessionManager } from '../session/session-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { ExchangeDataStream } from '../sse/exchange-data-stream';
import { SessionApi } from '../../api/session';
import { ConnectionStateManager } from './connection-state';
import { ConnectionQuality } from './connection-state';

export class ConnectionLifecycleManager extends EventEmitter {
  private stateManager: ConnectionStateManager;
  private tokenManager: TokenManager;
  private wsManager: WebSocketManager;
  private sseManager: ExchangeDataStream;
  private sessionApi: SessionApi;
  private heartbeatInterval: number | null = null;

  constructor(
    tokenManager: TokenManager,
    wsManager: WebSocketManager,
    sseManager: ExchangeDataStream,
    sessionApi: SessionApi,
  ) {
    super();
    this.stateManager = new ConnectionStateManager();
    this.tokenManager = tokenManager;
    this.wsManager = wsManager;
    this.sseManager = sseManager;
    this.sessionApi = sessionApi;

    this.setupEventListeners();
  }

  private setupEventListeners(): void {
    this.wsManager.on('connected', this.handleWsConnected.bind(this));
    this.wsManager.on('disconnected', this.handleWsDisconnected.bind(this));
    this.wsManager.on('heartbeat', this.handleHeartbeat.bind(this));
  }

  private handleWsConnected(): void {
    this.stateManager.updateState({ 
      isConnected: true, 
      isConnecting: false,
      error: null 
    });
    this.emit('connected');
    this.startHeartbeat();
  }

  private handleWsDisconnected(): void {
    this.stateManager.updateState({ 
      isConnected: false,
      isConnecting: false 
    });
    this.emit('disconnected');
    this.stopHeartbeat();
  }

  private handleHeartbeat(data: any): void {
    const now = Date.now();
    const latency = data.latency || (now - this.stateManager.getState().lastHeartbeatTime);
    
    this.stateManager.updateState({
      lastHeartbeatTime: now,
      heartbeatLatency: latency,
      missedHeartbeats: 0
    });
    
    let quality: ConnectionQuality = this.calculateConnectionQuality(latency);
    this.stateManager.updateState({ connectionQuality: quality });
    
    this.emit('heartbeat', { timestamp: now, latency });
  }

  private calculateConnectionQuality(latency: number): ConnectionQuality {
    if (latency <= 500) return 'good';
    if (latency <= 1000) return 'degraded';
    return 'poor';
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatInterval = window.setInterval(() => {
      if (!this.stateManager.getState().isConnected) return;
      
      this.wsManager.send({ 
        type: 'heartbeat', 
        timestamp: Date.now() 
      });
    }, 15000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  public async connect(): Promise<boolean> {
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      this.stateManager.updateState({ 
        error: 'Authentication required',
        isConnected: false,
        isConnecting: false
      });
      return false;
    }

    if (this.stateManager.getState().isConnected || 
        this.stateManager.getState().isConnecting) {
      return this.stateManager.getState().isConnected;
    }

    this.stateManager.updateState({ isConnecting: true, error: null });

    try {
      // Create or validate session first
      await this.ensureSession();
      
      // Connect main WebSocket 
      const wsConnected = await this.wsManager.connect();
      if (!wsConnected) {
        throw new Error('Failed to establish WebSocket connection');
      }
      
      // Only connect SSE after WebSocket is successful
      await this.sseManager.connect();
      
      this.stateManager.updateState({ 
        isConnected: true, 
        isConnecting: false 
      });
      
      return true;
    } catch (error) {
      this.handleConnectionError(error);
      return false;
    }
  }

  private async ensureSession(): Promise<void> {
    try {
      // Create session if needed - session ID is managed internally by the API
      const response = await this.sessionApi.createSession();
      
      if (!response.success) {
        throw new Error(response.errorMessage || 'Failed to create session');
      }
      
      // We don't need to explicitly store or pass the session ID anymore
      // The backend will associate the connection with the session
    } catch (error) {
      console.error('Session initialization error:', error);
      throw new Error('Failed to initialize session');
    }
  }

  private handleConnectionError(error: any): void {
    console.error('Connection error:', error);
    
    this.stateManager.updateState({ 
      isConnecting: false, 
      error: error instanceof Error ? error.message : 'Connection failed' 
    });
  }

  public disconnect(): void {
    this.wsManager.disconnect();
    this.sseManager.disconnect();
    this.stopHeartbeat();
    this.stateManager.reset();
  }

  public getState() {
    return this.stateManager.getState();
  }
}