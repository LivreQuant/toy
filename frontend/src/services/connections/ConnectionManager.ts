// src/services/connections/EnhancedConnectionManager.ts
import { BackoffStrategy } from './BackoffStrategy';
import { SessionStore, SessionData } from '../session/SessionStore';
import { createSession, getSession, keepAlive, getSessionState } from '../grpc/session';
import { getSimulatorStatus, startSimulator } from '../grpc/simulator';
import { SimulatorStatus } from '../../types/simulator';

export enum ConnectionState {
  DISCONNECTED = 'DISCONNECTED',
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  RECONNECTING = 'RECONNECTING',
  FAILED = 'FAILED'
}

export interface ConnectionEvent {
  type: 'state_change' | 'heartbeat' | 'reconnecting' | 'session' | 'simulator' | 'error';
  data: any;
}

export class EnhancedConnectionManager {
  private state: ConnectionState = ConnectionState.DISCONNECTED;
  private backoffStrategy: BackoffStrategy;
  private keepAliveInterval: NodeJS.Timeout | null = null;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private heartbeatInterval: NodeJS.Timeout | null = null;
  private maxReconnectAttempts = 10;
  private listeners: Map<string, Set<Function>> = new Map();
  
  // Heartbeat tracking
  private lastHeartbeatResponse: number = Date.now();
  private heartbeatTimeoutMs: number = 5000; // 5 seconds
  private consecutiveHeartbeatMisses: number = 0;
  private maxHeartbeatMisses: number = 3;
  
  // Session info
  private sessionId: string | null = null;
  private userId: string | null = null;
  private simulatorId: string | null = null;
  private simulatorStatus: SimulatorStatus = 'UNKNOWN';
  
  constructor() {
    this.backoffStrategy = new BackoffStrategy(1000, 30000); // Start at 1s, max 30s
    this.setupNetworkListeners();
  }
  
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
  
  private async checkAndReconnect(): Promise<void> {
    const session = SessionStore.getSession();
    if (!session || !session.token || !session.sessionId) {
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
    this.reconnect(session.token, session.sessionId, session.simulatorId);
  }
  
  public async connect(token: string): Promise<boolean> {
    this.setState(ConnectionState.CONNECTING);
    
    try {
      // Create new session
      const sessionResponse = await createSession(token);
      
      if (sessionResponse.success) {
        this.sessionId = sessionResponse.sessionId;
        
        // Store session data
        SessionStore.saveSession({
          token,
          sessionId: sessionResponse.sessionId,
          lastActive: Date.now(),
          reconnectAttempts: 0
        });
        
        this.setState(ConnectionState.CONNECTED);
        this.startKeepAlive();
        this.startHeartbeats();
        
        this.emit('session', { 
          valid: true, 
          new: true, 
          sessionId: sessionResponse.sessionId 
        });
        return true;
      } else {
        this.setState(ConnectionState.FAILED);
        this.emit('session', { 
          valid: false, 
          reason: 'create_failed', 
          error: sessionResponse.errorMessage 
        });
        return false;
      }
    } catch (error) {
      this.setState(ConnectionState.FAILED);
      this.emit('session', { 
        valid: false, 
        reason: 'network_error', 
        error 
      });
      return false;
    }
  }
  
  public async reconnect(token: string, sessionId: string, simulatorId?: string): Promise<boolean> {
    if (this.state === ConnectionState.RECONNECTING) {
      return false; // Already trying to reconnect
    }
    
    this.setState(ConnectionState.RECONNECTING);
    
    try {
      // Check if session is still valid
      const sessionResponse = await getSession(token, sessionId);
      
      if (sessionResponse.sessionActive) {
        // Session is still valid
        SessionStore.resetReconnectAttempts();
        this.sessionId = sessionId;
        
        // Get full session state
        const stateResponse = await getSessionState(token, sessionId);
        
        if (stateResponse.success) {
          this.simulatorId = stateResponse.simulatorId || null;
          
          // Update session data
          SessionStore.saveSession({
            token,
            sessionId,
            simulatorId: this.simulatorId,
            lastActive: Date.now()
          });
          
          this.setState(ConnectionState.CONNECTED);
          this.startKeepAlive();
          this.startHeartbeats();
          
          // If we have a simulator ID, check its status
          if (this.simulatorId) {
            this.checkSimulatorStatus(token, this.simulatorId);
          }
          
          this.emit('session', { 
            valid: true, 
            reconnected: true, 
            sessionId,
            simulatorId: this.simulatorId
          });
          return true;
        } else {
          // Session state retrieval failed
          return this.handleExpiredSession(token, simulatorId);
        }
      } else {
        // Session expired or invalid, need to create a new one
        return this.handleExpiredSession(token, simulatorId);
      }
    } catch (error) {
      // Network or other error
      return this.handleReconnectionError(token, sessionId, simulatorId, error);
    }
  }
  
  private async handleExpiredSession(token: string, simulatorId?: string): Promise<boolean> {
    console.log('Session expired. Creating a new session...');
    
    try {
      // Create new session
      const sessionResponse = await createSession(token);
      
      if (sessionResponse.success) {
        const newSessionId = sessionResponse.sessionId;
        this.sessionId = newSessionId;
        
        // Store new session
        SessionStore.saveSession({
          token,
          sessionId: newSessionId,
          lastActive: Date.now(),
          reconnectAttempts: 0
        });
        
        this.setState(ConnectionState.CONNECTED);
        this.startKeepAlive();
        this.startHeartbeats();
        
        // If we had a simulator, try to restart it
        if (simulatorId) {
          this.restartSimulator(token, newSessionId);
        }
        
        this.emit('session', { 
          valid: true, 
          reconnected: true, 
          sessionRenewed: true, 
          sessionId: newSessionId 
        });
        return true;
      } else {
        this.setState(ConnectionState.FAILED);
        this.emit('session', { 
          valid: false, 
          reason: 'create_failed', 
          error: sessionResponse.errorMessage 
        });
        return false;
      }
    } catch (error) {
      this.setState(ConnectionState.FAILED);
      this.emit('session', { 
        valid: false, 
        reason: 'network_error', 
        error 
      });
      return false;
    }
  }
  
  private async handleReconnectionError(
    token: string, 
    sessionId: string, 
    simulatorId?: string,
    error?: any
  ): Promise<boolean> {
    const attempts = SessionStore.incrementReconnectAttempts();
    
    if (attempts >= this.maxReconnectAttempts) {
      // Too many failures, give up
      this.setState(ConnectionState.FAILED);
      this.emit('session', { 
        valid: false, 
        reason: 'max_attempts_reached', 
        error 
      });
      return false;
    }
    
    // Schedule retry with exponential backoff
    const backoffTime = this.backoffStrategy.nextBackoffTime();
    console.log(`Reconnection attempt ${attempts} failed. Retrying in ${backoffTime}ms...`);
    
    this.reconnectTimeout = setTimeout(() => {
      this.reconnect(token, sessionId, simulatorId);
    }, backoffTime);
    
    this.emit('reconnecting', { 
      attempt: attempts, 
      maxAttempts: this.maxReconnectAttempts, 
      nextAttemptIn: backoffTime 
    });
    
    return false;
  }
  
  private async checkSimulatorStatus(token: string, simulatorId: string): Promise<void> {
    try {
      const statusResponse = await getSimulatorStatus(token, simulatorId);
      this.simulatorStatus = statusResponse.status;
      
      this.emit('simulator', {
        id: simulatorId,
        status: statusResponse.status,
        error: statusResponse.errorMessage
      });
    } catch (error) {
      console.error('Failed to check simulator status', error);
      this.simulatorStatus = 'ERROR';
      
      this.emit('simulator', {
        id: simulatorId,
        status: 'ERROR',
        error: error
      });
    }
  }
  
  private async restartSimulator(token: string, sessionId: string): Promise<void> {
    try {
      const response = await startSimulator(token, sessionId);
      
      if (response.success) {
        this.simulatorId = response.simulatorId;
        this.simulatorStatus = 'STARTING';
        
        // Update session with new simulator ID
        SessionStore.saveSession({
          simulatorId: response.simulatorId
        });
        
        this.emit('simulator', {
          id: response.simulatorId,
          status: 'STARTING',
          restarted: true
        });
      } else {
        this.simulatorId = null;
        this.simulatorStatus = 'ERROR';
        
        this.emit('simulator', {
          status: 'ERROR',
          error: response.errorMessage,
          restartFailed: true
        });
      }
    } catch (error) {
      console.error('Failed to restart simulator', error);
      this.simulatorId = null;
      this.simulatorStatus = 'ERROR';
      
      this.emit('simulator', {
        status: 'ERROR',
        error,
        restartFailed: true
      });
    }
  }
  
  private startKeepAlive(): void {
    this.clearIntervals();
    
    // Start keep-alive interval
    this.keepAliveInterval = setInterval(() => {
      this.sendKeepAlive();
    }, 30000); // Every 30 seconds
  }
  
  private startHeartbeats(): void {
    // Start more frequent heartbeats
    this.heartbeatInterval = setInterval(() => {
      this.sendHeartbeat();
    }, 5000); // Every 5 seconds
  }
  
  private async sendKeepAlive(): Promise<void> {
    const session = SessionStore.getSession();
    if (!session || !session.token || !session.sessionId) {
      return;
    }
    
    try {
      const success = await keepAlive(session.token, session.sessionId);
      
      if (success) {
        this.updateLastActivity();
      } else {
        console.warn('Keep-alive failed. Will attempt to reconnect...');
        this.checkAndReconnect();
      }
    } catch (error) {
      console.error('Keep-alive request failed', error);
      this.setState(ConnectionState.DISCONNECTED);
      this.checkAndReconnect();
    }
  }
  
  private async sendHeartbeat(): Promise<void> {
    const session = SessionStore.getSession();
    if (!session || !session.token || !session.sessionId) {
      return;
    }
    
    try {
      // Record time before heartbeat
      const heartbeatSentTime = Date.now();
      
      const success = await keepAlive(session.token, session.sessionId);
      
      if (success) {
        // Update last successful heartbeat time
        this.lastHeartbeatResponse = Date.now();
        this.consecutiveHeartbeatMisses = 0;
        
        // Calculate latency for monitoring
        const latency = this.lastHeartbeatResponse - heartbeatSentTime;
        
        // Emit heartbeat event with latency info
        this.emit('heartbeat', { 
          success: true, 
          latency,
          timestamp: this.lastHeartbeatResponse
        });
        
        // Update session activity
        this.updateLastActivity();
      } else {
        this.handleHeartbeatFailure('server_rejected');
      }
    } catch (error) {
      this.handleHeartbeatFailure('network_error', error);
    }
  }
  
  private handleHeartbeatFailure(reason: string, error?: any): void {
    this.consecutiveHeartbeatMisses++;
    
    this.emit('heartbeat', {
      success: false,
      reason,
      error,
      consecutiveMisses: this.consecutiveHeartbeatMisses,
      maxMisses: this.maxHeartbeatMisses
    });
    
    // If we've missed too many heartbeats in a row, consider connection lost
    if (this.consecutiveHeartbeatMisses >= this.maxHeartbeatMisses) {
      console.warn(`Missed ${this.consecutiveHeartbeatMisses} heartbeats. Connection considered unstable.`);
      
      if (this.state === ConnectionState.CONNECTED) {
        this.setState(ConnectionState.DISCONNECTED);
        this.checkAndReconnect();
      }
    }
  }
  
  private checkHeartbeatTimeout(): void {
    const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeatResponse;
    
    if (timeSinceLastHeartbeat > this.heartbeatTimeoutMs * 3) {
      console.warn(`No heartbeat response in ${timeSinceLastHeartbeat}ms. Connection considered unstable.`);
      
      if (this.state === ConnectionState.CONNECTED) {
        this.setState(ConnectionState.DISCONNECTED);
        this.checkAndReconnect();
      }
    }
  }
  
  private updateLastActivity(): void {
    SessionStore.updateActivity();
  }
  
  private clearIntervals(): void {
    if (this.keepAliveInterval) {
      clearInterval(this.keepAliveInterval);
      this.keepAliveInterval = null;
    }
    
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
  
  public disconnect(): void {
    this.clearIntervals();
    this.setState(ConnectionState.DISCONNECTED);
    this.sessionId = null;
    this.simulatorId = null;
    this.simulatorStatus = 'UNKNOWN';
    SessionStore.clearSession();
    this.emit('session', { valid: false, reason: 'user_logout' });
  }
  
  public getSessionId(): string | null {
    return this.sessionId;
  }
  
  public getSimulatorId(): string | null {
    return this.simulatorId;
  }
  
  public getSimulatorStatus(): SimulatorStatus {
    return this.simulatorStatus;
  }
  
  public getState(): ConnectionState {
    return this.state;
  }
  
  public isConnected(): boolean {
    return this.state === ConnectionState.CONNECTED;
  }
  
  public isReconnecting(): boolean {
    return this.state === ConnectionState.RECONNECTING;
  }
  
  public getConnectionQuality(): 'good' | 'degraded' | 'poor' {
    // Determine connection quality based on heartbeat performance
    const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeatResponse;
    
    if (this.state !== ConnectionState.CONNECTED) {
      return 'poor';
    }
    
    if (this.consecutiveHeartbeatMisses > 0 || timeSinceLastHeartbeat > this.heartbeatTimeoutMs) {
      return 'degraded';
    }
    
    return 'good';
  }
  
  private setState(newState: ConnectionState): void {
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
  
  public on(event: string, callback: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    
    this.listeners.get(event)?.add(callback);
  }
  
  public off(event: string, callback: Function): void {
    if (this.listeners.has(event)) {
      this.listeners.get(event)?.delete(callback);
    }
  }
  
  private emit(event: string, data: any): void {
    if (this.listeners.has(event)) {
      this.listeners.get(event)?.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in event listener for ${event}:`, error);
        }
      });
    }
    
    // Also emit to 'all' listeners
    if (this.listeners.has('all')) {
      this.listeners.get('all')?.forEach(callback => {
        try {
          callback({
            type: event,
            data: data
          } as ConnectionEvent);
        } catch (error) {
          console.error(`Error in 'all' event listener handling ${event}:`, error);
        }
      });
    }
  }
}