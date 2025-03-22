// src/services/connections/EnhancedConnectionManager.ts
import { BackoffStrategy } from './BackoffStrategy';
import { SessionStore } from '../session/SessionStore';
import { ConnectionState, ConnectionEvent, ConnectionEventType, ConnectionQuality } from './ConnectionTypes';
import { ConnectionNetworkManager } from './ConnectionNetworkManager';
import { getServiceConfig } from '../config/ServiceConfig';
import { EventEmitter } from './EventEmitter';
import { ConnectionHeartbeat } from './ConnectionHeartbeat';
import { ConnectionSession } from './ConnectionSession';
import { TokenManager } from '../auth/TokenManager';

export class EnhancedConnectionManager {
  // Core state
  private state: ConnectionState = ConnectionState.DISCONNECTED;
  private backoffStrategy: BackoffStrategy;
  private serviceConfig: any;
  private connectionQuality: ConnectionQuality = 'good';
  private tokenManager: TokenManager;
  
  // Interval timers
  private keepAliveInterval: NodeJS.Timeout | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  
  // Component modules
  private eventEmitter: EventEmitter;
  private heartbeat: ConnectionHeartbeat;
  private session: ConnectionSession;
  
  constructor(tokenManager: TokenManager) {
    this.tokenManager = tokenManager;
    this.serviceConfig = getServiceConfig();
    
    // Initialize backoff strategy
    this.backoffStrategy = new BackoffStrategy(
      this.serviceConfig.initialBackoffMs || 1000, 
      this.serviceConfig.maxBackoffMs || 30000
    );
    
    // Initialize component modules
    this.eventEmitter = new EventEmitter();
    this.heartbeat = new ConnectionHeartbeat(this, this.serviceConfig);
    this.session = new ConnectionSession(this, this.serviceConfig);
    
    // Setup network event listeners
    this.setupNetworkListeners();
  }
  
  // Event management
  public on(event: ConnectionEventType, callback: Function): void {
    this.eventEmitter.on(event, callback);
  }
  
  public off(event: ConnectionEventType, callback: Function): void {
    this.eventEmitter.off(event, callback);
  }
  
  public emit(event: ConnectionEventType, data: any): void {
    this.eventEmitter.emit(event, data);
  }
  
  // Network state listeners
  private setupNetworkListeners(): void {
    // Watch for online/offline events
    window.addEventListener('online', () => this.handleNetworkChange(true));
    window.addEventListener('offline', () => this.handleNetworkChange(false));
    
    // Set up visibility change detection for tab switching/browser minimizing
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        this.checkAndReconnect();
      }
    });
    
    // Check connection before unload to potentially save state
    window.addEventListener('beforeunload', () => {
      this.updateLastActivity();
    });
  }
  
  private handleNetworkChange(isOnline: boolean): void {
    if (isOnline) {
      console.log('Network connection restored. Attempting to reconnect...');
      this.checkAndReconnect();
    } else {
      console.log('Network connection lost. Will attempt reconnection when online.');
      this.setState(ConnectionState.DISCONNECTED);
      this.clearIntervals();
    }
  }
  
  // Connection state methods
  public getState(): ConnectionState {
    return this.state;
  }
  
  public setState(newState: ConnectionState): void {
    const oldState = this.state;
    this.state = newState;
    
    if (oldState !== newState) {
      this.emit('state_change', { 
        oldState, 
        newState, 
        timestamp: Date.now() 
      });
    }
  }
  
  public isConnected(): boolean {
    return this.state === ConnectionState.CONNECTED;
  }
  
  public isReconnecting(): boolean {
    return this.state === ConnectionState.RECONNECTING;
  }
  
  // Connection quality
  public getConnectionQuality(): ConnectionQuality {
    return this.connectionQuality;
  }
  
  public setConnectionQuality(quality: ConnectionQuality): void {
    if (this.connectionQuality !== quality) {
      this.connectionQuality = quality;
      this.emit('connection_quality', { quality });
    }
  }
  
  // Token management
  public getTokenManager(): TokenManager {
    return this.tokenManager;
  }
  
  public updateAuthToken(token: string): void {
    // Notify session about token update
    this.session.updateToken(token);
  }
  
  // Public API
  public async connect(token: string): Promise<boolean> {
    return this.session.connect(token);
  }
  
  public async reconnect(
    token: string, 
    sessionId: string, 
    simulatorId?: string
  ): Promise<boolean> {
    return this.session.reconnect(token, sessionId, simulatorId);
  }
  
  public async reconnectWithBackoff(): Promise<boolean> {
    // If we're already reconnecting, just wait for that to finish
    if (this.state === ConnectionState.RECONNECTING) {
      return new Promise<boolean>((resolve) => {
        const checkInterval = setInterval(() => {
          if (this.state === ConnectionState.CONNECTED) {
            clearInterval(checkInterval);
            resolve(true);
          } else if (this.state === ConnectionState.FAILED) {
            clearInterval(checkInterval);
            resolve(false);
          }
        }, 500);
        
        // Timeout after 30 seconds
        setTimeout(() => {
          clearInterval(checkInterval);
          resolve(false);
        }, 30000);
      });
    }
  
    // Start reconnection process
    this.setState(ConnectionState.RECONNECTING);
    this.backoffStrategy.reset(); // Reset backoff on new reconnection sequence
    
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      this.setState(ConnectionState.FAILED);
      this.emit('session', { valid: false, reason: 'no_token' });
      return false;
    }
    
    const session = SessionStore.getSession();
    if (!session || !session.sessionId) {
      this.setState(ConnectionState.FAILED);
      this.emit('session', { valid: false, reason: 'no_session_data' });
      return false;
    }
    
    let attempts = 0;
    let success = false;
    
    while (attempts < this.serviceConfig.maxReconnectAttempts && !success) {
      attempts++;
      
      try {
        this.emit('reconnecting', { 
          attempt: attempts, 
          maxAttempts: this.serviceConfig.maxReconnectAttempts 
        });
        
        // Try to reconnect using the explicit reconnect endpoint
        success = await this.session.reconnectSession(
          token, 
          session.sessionId, 
          attempts
        );
        
        if (success) {
          this.setState(ConnectionState.CONNECTED);
          return true;
        }
      } catch (error) {
        console.error(`Reconnection attempt ${attempts} failed:`, error);
        
        // Special handling for EKS/ALB connection resets
        if (ConnectionNetworkManager.isEksConnectionReset(error)) {
          console.warn('AWS ALB connection reset detected, using faster retry');
          // Use a shorter backoff time for ALB connection issues
          await new Promise(resolve => setTimeout(resolve, 1000));
        } else {
          // Standard backoff
          const backoffTime = this.backoffStrategy.nextBackoffTime();
          await new Promise(resolve => setTimeout(resolve, backoffTime));
        }
      }
    }
    
    if (!success) {
      this.setState(ConnectionState.FAILED);
      this.emit('session', { valid: false, reason: 'max_attempts_reached' });
    }
    
    return success;
  }
  
  public disconnect(): void {
    this.clearIntervals();
    this.setState(ConnectionState.DISCONNECTED);
    this.session.clearSession();
    this.emit('session', { valid: false, reason: 'user_logout' });
  }
  
  // Session state
  public getSessionId(): string | null {
    return this.session.getSessionId();
  }
  
  public getSimulatorId(): string | null {
    return this.session.getSimulatorId();
  }
  
  public getSimulatorStatus(): string {
    return this.session.getSimulatorStatus();
  }
  
  // Heartbeat management
  public getLastHeartbeatTime(): number {
    return this.heartbeat.getLastHeartbeatTime();
  }
  
  public getHeartbeatLatency(): number | null {
    return this.heartbeat.getHeartbeatLatency();
  }
  
  // Activity management
  public updateLastActivity(): void {
    SessionStore.updateActivity();
  }
  
  // Helper methods
  public async checkAndReconnect(): Promise<void> {
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      // No token available, can't reconnect
      this.emit('session', { valid: false, reason: 'no_token' });
      return;
    }
    
    const session = SessionStore.getSession();
    if (!session || !session.sessionId) {
      // No session data available
      this.emit('session', { valid: false, reason: 'no_session_data' });
      return;
    }
    
    if (this.state === ConnectionState.CONNECTED) {
      // Already connected, just update activity
      this.updateLastActivity();
      return;
    }
    
    // Attempt to reconnect
    this.reconnect(token, session.sessionId, session.simulatorId);
  }
  
  // Interval management
  public startKeepAlive(): void {
    this.heartbeat.startHeartbeats();
  }
  
  public clearIntervals(): void {
    if (this.keepAliveInterval) {
      clearInterval(this.keepAliveInterval);
      this.keepAliveInterval = null;
    }
    
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    this.heartbeat.clearIntervals();
  }
  
  // Connection quality monitoring
  public async updateConnectionQuality(): Promise<void> {
    const token = await this.tokenManager.getAccessToken();
    if (!token) return;
    
    const session = SessionStore.getSession();
    if (!session || !session.sessionId || !this.isConnected()) {
      return;
    }
    
    try {
      // Calculate metrics
      const metrics = {
        sessionId: session.sessionId,
        token: token,
        latencyMs: this.heartbeat.getHeartbeatLatency() || 0,
        missedHeartbeats: this.heartbeat.getConsecutiveMisses(),
        connectionType: ConnectionNetworkManager.detectConnectionType()
      };
      
      const url = ConnectionNetworkManager.createServiceUrl('session', 'connection-quality');
      const response = await fetch(url, {
        method: 'POST',
        ...ConnectionNetworkManager.getFetchOptions({
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify(metrics)
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        
        // Update connection quality
        if (data.quality) {
          this.setConnectionQuality(data.quality);
        }
        
        // Check if server recommends reconnection
        if (data.reconnectRecommended) {
          console.warn('Server recommends reconnection due to poor connection quality');
          if (this.state === ConnectionState.CONNECTED) {
            this.reconnectWithBackoff();
          }
        }
      }
    } catch (error) {
      console.error('Failed to update connection quality:', error);
    }
  }
}