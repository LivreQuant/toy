// src/services/connections/ConnectionSession.ts
import { ConnectionState } from './ConnectionTypes';
import { EnhancedConnectionManager } from './EnhancedConnectionManager';
import { ConnectionNetworkManager } from './ConnectionNetworkManager';
import { SessionStore } from '../session/SessionStore';

export class ConnectionSession {
  private manager: EnhancedConnectionManager;
  private config: any;
  
  // Session info
  private sessionId: string | null = null;
  private userId: string | null = null;
  private simulatorId: string | null = null;
  private simulatorStatus: string = 'UNKNOWN';
  private currentPodId: string | null = null;
  
  // Stream tracking
  private activeStreams: Map<string, any> = new Map();
  private streamReconnectAttempts: number = 0;
  private maxStreamReconnectAttempts: number = 5;
  
  constructor(manager: EnhancedConnectionManager, config: any) {
    this.manager = manager;
    this.config = config;
  }
  
  // Session management
  public async connect(token: string): Promise<boolean> {
    this.manager.setState(ConnectionState.CONNECTING);
    
    try {
      // Create new session
      const url = ConnectionNetworkManager.createServiceUrl('session', 'create');
      const response = await fetch(url, {
        method: 'POST',
        ...ConnectionNetworkManager.getFetchOptions({
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
      });
      
      if (!response.ok) {
        throw new Error(`Failed to create session: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.success) {
        this.sessionId = data.sessionId;
        
        // Capture pod info if available
        if (data.podName) {
          this.currentPodId = data.podName;
        }
        
        // Store session data
        SessionStore.saveSession({
          token,
          sessionId: data.sessionId,
          lastActive: Date.now(),
          reconnectAttempts: 0,
          podName: data.podName
        });
        
        this.manager.setState(ConnectionState.CONNECTED);
        this.manager.startKeepAlive();
        
        this.manager.emit('session', { 
          valid: true, 
          new: true, 
          sessionId: data.sessionId,
          podName: data.podName
        });
        return true;
      } else {
        this.manager.setState(ConnectionState.FAILED);
        this.manager.emit('session', { 
          valid: false, 
          reason: 'create_failed', 
          error: data.errorMessage 
        });
        return false;
      }
    } catch (error) {
      this.manager.setState(ConnectionState.FAILED);
      this.manager.emit('session', { 
        valid: false, 
        reason: 'network_error', 
        error 
      });
      return false;
    }
  }
  
  public async reconnect(token: string, sessionId: string, simulatorId?: string): Promise<boolean> {
    if (this.manager.getState() === ConnectionState.RECONNECTING) {
      return false; // Already trying to reconnect
    }
    
    this.manager.setState(ConnectionState.RECONNECTING);
    
    try {
      // Check if session is still valid
      const url = ConnectionNetworkManager.createServiceUrl('session', 'get');
      const response = await fetch(`${url}?sessionId=${sessionId}`, {
        method: 'GET',
        ...ConnectionNetworkManager.getFetchOptions({
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
      });
      
      if (!response.ok) {
        throw new Error(`Failed to check session: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.sessionActive) {
        // Session is still valid
        SessionStore.resetReconnectAttempts();
        this.sessionId = sessionId;
        
        // Update pod info if available
        if (data.podName && this.currentPodId !== data.podName) {
          const oldPod = this.currentPodId;
          this.currentPodId = data.podName;
          
          // Notify about pod change
          this.manager.emit('pod_switched', {
            oldPod,
            newPod: data.podName
          });
        }
        
        // Update simulator status
        if (data.simulatorId) {
          this.simulatorId = data.simulatorId;
          this.simulatorStatus = data.simulatorStatus || 'UNKNOWN';
        }
        
        // Update session data
        SessionStore.saveSession({
          token,
          sessionId,
          simulatorId: this.simulatorId,
          podName: data.podName,
          lastActive: Date.now()
        });
        
        this.manager.setState(ConnectionState.CONNECTED);
        this.manager.startKeepAlive();
        
        this.manager.emit('session', { 
          valid: true, 
          reconnected: true, 
          sessionId,
          simulatorId: this.simulatorId,
          podName: data.podName
        });
        
        // Reconnect any active streams
        this.reconnectAllStreams();
        
        return true;
      } else {
        // Session expired or invalid, need to create a new one
        return this.handleExpiredSession(token, simulatorId);
      }
    } catch (error) {
      // Network or other error
      console.error('Error reconnecting:', error);
      
      // Special handling for EKS-specific errors
      if (ConnectionNetworkManager.isEksConnectionReset(error)) {
        console.warn('EKS connection reset detected, attempting faster retry');
        await new Promise(resolve => setTimeout(resolve, 1000));
        return this.reconnect(token, sessionId, simulatorId);
      }
      
      // Special handling for HTTP/2 stream errors
      if (ConnectionNetworkManager.isStreamError(error)) {
        console.warn('HTTP/2 stream error detected, will attempt reconnection');
        // Use shorter backoff for stream errors
        await new Promise(resolve => setTimeout(resolve, 1500));
        return this.reconnect(token, sessionId, simulatorId);
      }
      
      // Standard error handling
      const attempts = SessionStore.incrementReconnectAttempts();
      this.manager.emit('reconnecting', { attempt: attempts });
      return false;
    }
  }
  
  public async reconnectSession(
    token: string, 
    sessionId: string, 
    attempt: number
  ): Promise<boolean> {
    try {
      // Call the explicit reconnect endpoint
      const url = ConnectionNetworkManager.createServiceUrl('session', 'reconnect');
      const response = await fetch(url, {
        method: 'POST',
        ...ConnectionNetworkManager.getFetchOptions({
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            sessionId,
            reconnectAttempt: attempt
          })
        })
      });
      
      if (!response.ok) {
        throw new Error(`Reconnection failed: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      if (data.success) {
        this.sessionId = data.sessionId;
        this.simulatorId = data.simulatorId || null;
        this.simulatorStatus = data.simulatorStatus || 'UNKNOWN';
        
        // Check if pod host changed
        if (data.podName) {
          const podSwitched = this.currentPodId && this.currentPodId !== data.podName;
          const oldPod = this.currentPodId;
          this.currentPodId = data.podName;
          
          if (podSwitched) {
            console.log(`Pod affinity changed to ${data.podName}`);
            this.manager.emit('pod_switched', { 
              oldPod,
              newPod: data.podName 
            });
          }
        }
        
        // Update stored session
        SessionStore.saveSession({
          token,
          sessionId: data.sessionId,
          simulatorId: data.simulatorId || null,
          podName: data.podName || null,
          lastActive: Date.now(),
          reconnectAttempts: 0
        });
        
        this.manager.startKeepAlive();
        
        this.manager.emit('session', {
          valid: true,
          reconnected: true,
          sessionId: data.sessionId,
          simulatorId: data.simulatorId || null,
          simulatorStatus: data.simulatorStatus || 'UNKNOWN',
          podName: data.podName
        });
        
        // Reconnect any active streams
        this.reconnectAllStreams();
        
        return true;
      } else {
        throw new Error(data.errorMessage || 'Reconnection failed');
      }
    } catch (error) {
      console.error('Failed to reconnect session:', error);
      
      // Check for specific EKS errors
      if (ConnectionNetworkManager.isEksConnectionReset(error) || 
          ConnectionNetworkManager.isStreamError(error)) {
        console.warn('EKS-specific error detected, using shorter retry delay');
        // Don't throw - allow caller to retry with shorter delay
        return false;
      }
      
      throw error;
    }
  }
  
  private async handleExpiredSession(token: string, simulatorId?: string): Promise<boolean> {
    console.log('Session expired. Creating a new session...');
    
    try {
      // Create new session
      const success = await this.connect(token);
      
      if (success && simulatorId) {
        // If we had a simulator, notify about the change
        this.manager.emit('simulator', {
          id: null,
          status: 'EXPIRED',
          needsRestart: true
        });
      }
      
      return success;
    } catch (error) {
      console.error('Failed to create new session after expiration:', error);
      return false;
    }
  }
  
  // Stream management
  public registerStream(streamId: string, streamObj: any): void {
    this.activeStreams.set(streamId, streamObj);
  }
  
  public unregisterStream(streamId: string): void {
    this.activeStreams.delete(streamId);
  }
  
  private async reconnectAllStreams(): Promise<void> {
    if (this.activeStreams.size === 0) return;
    
    console.log(`Attempting to reconnect ${this.activeStreams.size} active streams`);
    
    for (const [streamId, streamObj] of this.activeStreams.entries()) {
      try {
        if (typeof streamObj.reconnect === 'function') {
          await streamObj.reconnect();
        }
      } catch (error) {
        console.error(`Failed to reconnect stream ${streamId}:`, error);
      }
    }
  }
  
  public async reconnectStream(streamId: string): Promise<boolean> {
    const streamObj = this.activeStreams.get(streamId);
    if (!streamObj) return false;
    
    this.streamReconnectAttempts++;
    
    try {
      if (typeof streamObj.reconnect === 'function') {
        await streamObj.reconnect();
        this.streamReconnectAttempts = 0;
        return true;
      }
    } catch (error) {
      console.error(`Failed to reconnect stream ${streamId}:`, error);
      
      // If we've tried too many times, stop
      if (this.streamReconnectAttempts >= this.maxStreamReconnectAttempts) {
        console.error(`Maximum stream reconnect attempts (${this.maxStreamReconnectAttempts}) reached for ${streamId}`);
        return false;
      }
      
      // Special handling for EKS-specific errors
      if (ConnectionNetworkManager.isEksConnectionReset(error) || 
          ConnectionNetworkManager.isStreamError(error)) {
        console.warn('EKS-specific stream error detected, retrying with shorter delay');
        await new Promise(resolve => setTimeout(resolve, 1000));
        return this.reconnectStream(streamId);
      }
    }
    
    return false;
  }
  
  public async closeExchangeConnections(): Promise<void> {
    // Close all active connections to exchange services
    with this.lock:
      for session_id, connections in list(this.exchange_connections.items()):
        try {
          this._close_exchange_connection(session_id);
        } catch (e) {
          logger.error(`Error closing exchange connection for ${session_id}: ${e}`);
        }
  }
  
  public async initializeExchangeConnection(): Promise<boolean> {
    const session = SessionStore.getSession();
    if (!session || !session.sessionId) return false;
    
    try {
      // Get simulator info
      const sessionState = await this._getSessionState(session.sessionId, session.token);
      
      if (sessionState && sessionState.simulatorId && sessionState.simulatorEndpoint) {
        // Register in database
        return await this._activateExchangeService(
          session.sessionId,
          sessionState.simulatorId,
          sessionState.simulatorEndpoint
        );
      }
      return false;
    } catch (error) {
      logger.error(`Failed to initialize exchange connection: ${error}`);
      return false;
    }
  }

  private async _getSessionState(sessionId: string, token: string): Promise<any> {
    const url = ConnectionNetworkManager.createServiceUrl('session', 'state');
    const response = await fetch(`${url}?sessionId=${sessionId}`, {
      method: 'GET',
      ...ConnectionNetworkManager.getFetchOptions({
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
    });
    
    if (!response.ok) return null;
    return await response.json();
  }

  private async _activateExchangeService(
    sessionId: string, 
    simulatorId: string, 
    endpoint: string
  ): Promise<boolean> {
    // Register connection
    this.exchange_connections[sessionId] = {
      simulatorId,
      endpoint,
      active: true,
      lastActive: Date.now()
    };
    
    // Update session metadata
    SessionStore.updateSessionData(sessionId, {
      simulatorId,
      simulatorEndpoint: endpoint
    });
    
    return true;
  }

  // Session management
  public clearSession(): void {
    // Close all active streams
    for (const [streamId, streamObj] of this.activeStreams.entries()) {
      try {
        if (typeof streamObj.close === 'function') {
          streamObj.close();
        }
      } catch (e) {
        console.error(`Error closing stream ${streamId}:`, e);
      }
    }
    
    this.activeStreams.clear();
    this.sessionId = null;
    this.simulatorId = null;
    this.simulatorStatus = 'UNKNOWN';
    this.currentPodId = null;
    this.streamReconnectAttempts = 0;
    SessionStore.clearSession();
  }
  
  // Update session with new token
  public updateToken(token: string): void {
    const session = SessionStore.getSession();
    if (session && this.sessionId) {
      SessionStore.saveSession({
        ...session,
        token: token
      });
    }
  }
  
  // Getters
  public getSessionId(): string | null {
    return this.sessionId;
  }
  
  public getSimulatorId(): string | null {
    return this.simulatorId;
  }
  
  public getSimulatorStatus(): string {
    return this.simulatorStatus;
  }
  
  public getCurrentPodId(): string | null {
    return this.currentPodId;
  }
  
  // Stream statistics
  public getActiveStreamCount(): number {
    return this.activeStreams.size;
  }
}