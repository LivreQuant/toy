// src/services/connection/connection-lifecycle.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { SessionManager } from '../session/session-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { ExchangeDataStream } from '../sse/exchange-data-stream';
import { SessionApi } from '../../api/session';
import { HttpClient } from '../../api/http-client';
import { ConnectionStateManager } from './connection-state';
import { ConnectionQuality } from './connection-state';

export class ConnectionLifecycleManager extends EventEmitter {
  private stateManager: ConnectionStateManager;
  private tokenManager: TokenManager;
  private wsManager: WebSocketManager;
  private sseManager: ExchangeDataStream;
  private sessionApi: SessionApi;
  private httpClient: HttpClient;
  private heartbeatInterval: number | null = null;

  constructor(
    tokenManager: TokenManager,
    wsManager: WebSocketManager,
    sseManager: ExchangeDataStream,
    sessionApi: SessionApi,
    httpClient: HttpClient
  ) {
    super();
    this.stateManager = new ConnectionStateManager();
    this.tokenManager = tokenManager;
    this.wsManager = wsManager;
    this.sseManager = sseManager;
    this.sessionApi = sessionApi;
    this.httpClient = httpClient;

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
      const sessionId = await this.createOrGetSession();
      await this.checkSessionReadiness(sessionId);
      await this.connectWebSocket(sessionId);
      await this.connectMarketDataStream(sessionId);

      return true;
    } catch (error) {
      this.handleConnectionError(error);
      return false;
    }
  }

  private async createOrGetSession(): Promise<string> {
    let sessionId = SessionManager.getSessionId();
    
    if (!sessionId) {
      const response = await this.sessionApi.createSession();
      
      if (!response.success) {
        throw new Error(response.errorMessage || 'Failed to create session');
      }
      
      sessionId = response.sessionId;
      SessionManager.setSessionId(sessionId);
    }

    return sessionId;
  }

  private async checkSessionReadiness(sessionId: string): Promise<void> {
    const maxAttempts = 5;
    const retryDelay = 1000;

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        const ready = await this.sessionApi.checkSessionReady(sessionId);
        
        if (ready.success) return;
        
        if (attempt < maxAttempts) {
          await new Promise(resolve => setTimeout(resolve, retryDelay));
        }
      } catch (error) {
        if (attempt === maxAttempts) {
          throw new Error('Session readiness check failed');
        }
        await new Promise(resolve => setTimeout(resolve, retryDelay));
      }
    }
  }

  private async connectWebSocket(sessionId: string): Promise<void> {
    const wsConnected = await this.wsManager.connect(sessionId);
    
    if (!wsConnected) {
      throw new Error('Failed to establish WebSocket connection');
    }
  }

  private async connectMarketDataStream(sessionId: string): Promise<void> {
    await this.sseManager.connect(sessionId);
    
    this.stateManager.updateState({ 
      isConnected: true, 
      isConnecting: false 
    });
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
    SessionManager.clearSession();
    this.stateManager.reset();
  }

  public getState() {
    return this.stateManager.getState();
  }
}