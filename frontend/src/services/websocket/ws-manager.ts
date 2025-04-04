// src/services/websocket/ws-manager.ts
import { TokenManager } from '../auth/token-manager';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { EventEmitter } from '../../utils/event-emitter';
import { config } from '../../config';
import { toastService } from '../notification/toast-service';

export interface WebSocketOptions {
  heartbeatInterval?: number;
  reconnectMaxAttempts?: number;
  heartbeatTimeoutMs?: number;
  circuitBreakerThreshold?: number;
  circuitBreakerResetTimeMs?: number;
  connectionQualityBufferSize?: number;
}

export type ConnectionQuality = 'good' | 'degraded' | 'poor';

export class WebSocketManager extends EventEmitter {
  private ws: WebSocket | null = null;
  private url: string;
  private isConnecting: boolean = false;
  private backoffStrategy: BackoffStrategy;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private heartbeatTimeout: number | null = null;
  private lastHeartbeatResponse: number = 0;
  private tokenManager: TokenManager;
  private reconnectAttempt: number = 0;
  private maxReconnectAttempts: number;
  private heartbeatInterval: number;
  private heartbeatTimeoutMs: number;
  private heartbeatRtts: number[] = []; // Store recent round-trip times
  private lastHeartbeatSent: number = 0;
  private connectionQualityBufferSize: number;
  private pendingResponses: Map<string, { 
    resolve: (value: any) => void, 
    reject: (reason: any) => void,
    timeout: number 
  }> = new Map();
  
  // Circuit breaker properties
  private consecutiveFailures: number = 0;
  private circuitBreakerThreshold: number;
  private circuitBreakerState: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private circuitBreakerResetTime: number;
  private circuitBreakerTrippedAt: number = 0;
  
  // Session state
  private sessionId: string | null = null;
  private isMaster: boolean = false;
  private simulatorStatus: string = 'UNKNOWN';
  private simulatorId: string | null = null;
  
  constructor(tokenManager: TokenManager, options: WebSocketOptions = {}) {
    super();
    this.url = config.wsBaseUrl;
    this.tokenManager = tokenManager;
    this.backoffStrategy = new BackoffStrategy(1000, 30000);
    this.maxReconnectAttempts = options.reconnectMaxAttempts || 15;
    this.heartbeatInterval = options.heartbeatInterval || 15000; // 15 seconds
    this.heartbeatTimeoutMs = options.heartbeatTimeoutMs || 5000; // 5 seconds
    this.connectionQualityBufferSize = options.connectionQualityBufferSize || 10;
    
    // Circuit breaker configuration
    this.circuitBreakerThreshold = options.circuitBreakerThreshold || 5;
    this.circuitBreakerResetTime = options.circuitBreakerResetTimeMs || 60000; // 1 minute
  }
  
  public async connect(createNewSession: boolean = false): Promise<boolean> {
    // First check if token is available
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      this.emit('error', { error: 'No authentication token available' });
      return false;
    }

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return true;
    }
    
    if (this.isConnecting) {
      return new Promise<boolean>(resolve => {
        this.once('connected', () => resolve(true));
        this.once('connection_failed', () => resolve(false));
      });
    }
    
    // Check circuit breaker status
    if (this.circuitBreakerState === 'OPEN') {
      const currentTime = Date.now();
      if (currentTime - this.circuitBreakerTrippedAt < this.circuitBreakerResetTime) {
        // Circuit is open, fast fail the connection attempt
        this.emit('circuit_open', { 
          message: 'Connection attempts temporarily suspended due to repeated failures',
          resetTimeMs: this.circuitBreakerResetTime - (currentTime - this.circuitBreakerTrippedAt)
        });
        return false;
      } else {
        // Allow one attempt to try to reconnect (half-open state)
        this.circuitBreakerState = 'HALF_OPEN';
        this.emit('circuit_half_open', { 
          message: 'Trying one connection attempt after circuit breaker timeout'
        });
      }
    }
    
    this.isConnecting = true;
    
    try {
      // Construct URL with connection parameters
      const deviceId = this.generateDeviceId();
      const params = new URLSearchParams({
        token,
        deviceId,
        createSession: createNewSession.toString(),
        reconnectAttempt: this.reconnectAttempt.toString(),
        userAgent: navigator.userAgent
      });
      
      const wsUrl = `${this.url}?${params.toString()}`;
      this.ws = new WebSocket(wsUrl);
      
      return new Promise<boolean>((resolve) => {
        if (!this.ws) {
          this.isConnecting = false;
          this.handleConnectionFailure();
          this.emit('connection_failed', { error: 'Failed to create WebSocket' });
          resolve(false);
          return;
        }
        
        // Handle WebSocket events
        this.ws.onopen = () => {
          this.isConnecting = false;
          this.reconnectAttempt = 0;
          this.backoffStrategy.reset();
          this.lastHeartbeatResponse = Date.now();
          
          // Reset circuit breaker on successful connection
          this.consecutiveFailures = 0;
          if (this.circuitBreakerState === 'HALF_OPEN') {
            this.circuitBreakerState = 'CLOSED';
            this.emit('circuit_closed', { message: 'Circuit breaker reset after successful connection' });
          }
          
          this.emit('connected', { connected: true });
          this.startHeartbeat();
          
          // Immediately request session state
          this.requestSessionState();
          
          resolve(true);
        };
        
        this.ws.onclose = (event) => {
          this.handleDisconnect(event);
          if (this.isConnecting) {
            this.isConnecting = false;
            this.handleConnectionFailure();
            this.emit('connection_failed', { 
              code: event.code, 
              reason: event.reason || 'Connection closed during connect' 
            });
            resolve(false);
          }
        };
        
        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.emit('error', { error });
          if (this.isConnecting) {
            this.isConnecting = false;
            this.handleConnectionFailure();
            this.emit('connection_failed', { error: 'WebSocket connection error' });
            resolve(false);
          }
        };

        this.ws.onmessage = (event) => {
          this.handleMessage(event);
        };
      });
    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.isConnecting = false;
      this.handleConnectionFailure();
      this.emit('connection_failed', { error });
      return false;
    }
  }
  
  private generateDeviceId(): string {
    // Get stored device ID from local storage or create a new one
    const storageKey = 'trading_device_id';
    let deviceId = localStorage.getItem(storageKey);
    
    if (!deviceId) {
      deviceId = `device_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      localStorage.setItem(storageKey, deviceId);
    }
    
    return deviceId;
  }
  
  // Request current session state
  private async requestSessionState(): Promise<void> {
    try {
      const response = await this.sendWithResponse({
        type: 'get_session_state',
        timestamp: Date.now()
      });
      
      if (response.success) {
        this.sessionId = response.sessionId;
        this.isMaster = response.isMaster;
        this.simulatorStatus = response.simulatorStatus || 'UNKNOWN';
        this.simulatorId = response.simulatorId;
        
        // Emit session info for UI components
        this.emit('session_state', {
          sessionId: this.sessionId,
          isMaster: this.isMaster,
          simulatorStatus: this.simulatorStatus,
          simulatorId: this.simulatorId
        });
        
        // Also emit specific simulator update
        this.emit('simulator_update', {
          status: this.simulatorStatus,
          simulatorId: this.simulatorId
        });
      }
    } catch (error) {
      console.error('Failed to get session state:', error);
    }
  }
  
  private handleConnectionFailure() {
    // Increment failure counter
    this.consecutiveFailures++;
    
    // Check if we should trip the circuit breaker
    if (this.circuitBreakerState !== 'OPEN' && this.consecutiveFailures >= this.circuitBreakerThreshold) {
      this.circuitBreakerState = 'OPEN';
      this.circuitBreakerTrippedAt = Date.now();
      this.emit('circuit_trip', { 
        message: 'Circuit breaker tripped due to consecutive connection failures',
        failureCount: this.consecutiveFailures,
        resetTimeMs: this.circuitBreakerResetTime
      });
      
      // Notify about critical connection issue
      this.notifyConnectionIssue('critical');
    }

    // Critical connection issue toast
    if (this.consecutiveFailures >= this.circuitBreakerThreshold) {
      toastService.error('Multiple connection failures. Please check your network.', 10000);
    }
  }
  
  // Rest of methods below are mostly unchanged, just simplified

  public disconnect(): void {
    this.stopHeartbeat();
    this.stopReconnectTimer();
    this.clearPendingResponses();
    
    if (this.ws) {
      // Use code 1000 for normal closure
      this.ws.close(1000, 'Client disconnected');
      this.ws = null;
    }
    
    this.emit('disconnected', { reason: 'user_disconnect' });
  }
  
  public send(data: any): boolean {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false;
    }
    
    try {
      this.ws.send(typeof data === 'string' ? data : JSON.stringify(data));
      return true;
    } catch (error) {
      console.error('Error sending WebSocket message:', error);
      return false;
    }
  }
  
  private handleMessage(event: MessageEvent): void {
    try {
      // Reset heartbeat timeout on any message
      this.lastHeartbeatResponse = Date.now();
      
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = null;
      }
      
      // Parse message
      const message = JSON.parse(event.data);
      
      // Handle special message types
      if (message.type === 'heartbeat') {
        // Calculate RTT for this heartbeat
        if (this.lastHeartbeatSent > 0) {
          const rtt = Date.now() - this.lastHeartbeatSent;
          this.updateHeartbeatRtts(rtt);
        }
        
        this.emit('heartbeat', { 
          timestamp: Date.now(),
          rtt: this.lastHeartbeatSent > 0 ? Date.now() - this.lastHeartbeatSent : null
        });
        return;
      }
      
      // Handle session state update
      if (message.type === 'session_state') {
        this.sessionId = message.sessionId;
        this.isMaster = message.isMaster;
        this.simulatorStatus = message.simulatorStatus || this.simulatorStatus;
        this.simulatorId = message.simulatorId || this.simulatorId;
        
        this.emit('session_state', {
          sessionId: this.sessionId,
          isMaster: this.isMaster,
          simulatorStatus: this.simulatorStatus,
          simulatorId: this.simulatorId
        });
        
        if (message.simulatorStatus) {
          this.emit('simulator_update', {
            status: message.simulatorStatus,
            simulatorId: message.simulatorId
          });
        }
        
        return;
      }
      
      // Handle session_invalidated message
      if (message.type === 'session_invalidated') {
        this.handleSessionInvalidation(message.reason || 'Session invalidated by server', message);
        return;
      }
      
      // Handle master_changed message
      if (message.type === 'master_changed') {
        this.isMaster = message.isMaster;
        
        this.emit('master_status_changed', { 
          isMaster: this.isMaster,
          newMasterDeviceId: message.deviceId
        });
        
        // If this is a forced master change, show a notification
        if (message.forced) {
          toastService.warning('Another device has taken control of your trading session', 8000);
        }
        
        return;
      }
      
      // Check for response to a pending request
      if (message.requestId && this.pendingResponses.has(message.requestId)) {
        const { resolve, timeout } = this.pendingResponses.get(message.requestId)!;
        clearTimeout(timeout);
        this.pendingResponses.delete(message.requestId);
        resolve(message);
      }
      
      // Emit event based on message type
      if (message.type) {
        this.emit(message.type, message.data || message);
      }
      
      // Always emit the raw message as 'message'
      this.emit('message', message);
    } catch (error) {
      console.error('Error handling WebSocket message:', error);
    }
  }
  
  // Handle WebSocket disconnect
  private handleDisconnect(event: CloseEvent): void {
    this.stopHeartbeat();
    this.clearPendingResponses();
    
    const wasClean = event.wasClean;
    const code = event.code;
    const reason = event.reason || 'Unknown reason';
    
    console.log(`WebSocket disconnected: ${reason} (${code})`);
    
    this.emit('disconnected', { 
      wasClean, 
      code, 
      reason 
    });
    
    // Don't reconnect if this was a clean closure
    if (wasClean && code === 1000) {
      return;
    }
    
    // Handle session invalidation codes
    if (code === 4001) { // Custom code for invalid session
      this.handleSessionInvalidation('Session no longer valid');
      return;
    }
    
    // Increment failure counter for non-clean disconnects
    if (!wasClean) {
      this.handleConnectionFailure();
      this.notifyConnectionIssue(this.reconnectAttempt > 3 ? 'critical' : 'warning');
    }
    
    // Attempt to reconnect if circuit breaker allows
    if (this.circuitBreakerState !== 'OPEN') {
      this.attemptReconnect();
    }

    toastService.error('WebSocket connection lost', 7000);
    
    this.emit('connection_lost', {
      reason: event.reason || 'Unexpected disconnection',
      code: event.code
    });
  }
  
  // Handle session invalidation
  private handleSessionInvalidation(reason: string, data?: any): void {
    this.disconnect();
    
    this.emit('session_invalidated', { 
      reason,
      ...data
    });
    
    toastService.error(`Session ended: ${reason}`, 10000);
  }
  
  // Attempt reconnection with exponential backoff
  private attemptReconnect(): void {
    if (this.reconnectTimer !== null) {
      return; // Already trying to reconnect
    }
    
    if (this.reconnectAttempt >= this.maxReconnectAttempts) {
      this.emit('max_reconnect_attempts', { attempts: this.reconnectAttempt });
      this.notifyConnectionIssue('critical');
      return;
    }
    
    this.reconnectAttempt++;
    const delay = this.backoffStrategy.nextBackoffTime();
    
    this.emit('reconnecting', { 
      attempt: this.reconnectAttempt, 
      maxAttempts: this.maxReconnectAttempts,
      delay
    });
    
    this.reconnectTimer = window.setTimeout(async () => {
      this.reconnectTimer = null;
      
      // Pass false to not create a new session, attempt to reconnect to existing one
      const connected = await this.connect(false);
      
      if (!connected && this.circuitBreakerState !== 'OPEN') {
        // If connection failed, try again
        this.attemptReconnect();
      }
    }, delay);

    toastService.warning(`Reconnecting (Attempt ${this.reconnectAttempt})...`, 5000);
  }
  
  // Claim master status for this device
  public async claimMasterStatus(force: boolean = false): Promise<boolean> {
    try {
      const response = await this.sendWithResponse({
        type: 'claim_master',
        force,
        timestamp: Date.now()
      });
      
      if (response.success) {
        this.isMaster = true;
      }
      
      return response.success;
    } catch (error) {
      console.error('Failed to claim master status:', error);
      return false;
    }
  }
  
  // Get current session state
  public getSessionState(): {
    sessionId: string | null;
    isMaster: boolean;
    simulatorStatus: string;
    simulatorId: string | null;
    isConnected: boolean;
  } {
    return {
      sessionId: this.sessionId,
      isMaster: this.isMaster,
      simulatorStatus: this.simulatorStatus,
      simulatorId: this.simulatorId,
      isConnected: this.ws?.readyState === WebSocket.OPEN
    };
  }
  
  // Get connection health metrics
  public getConnectionHealth(): {
    status: 'connected' | 'connecting' | 'disconnected';
    lastHeartbeat: number;
    circuitStatus: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
    reconnectAttempts: number;
    avgRtt: number | null;
  } {
    const avgRtt = this.heartbeatRtts.length > 0 
      ? this.heartbeatRtts.reduce((a, b) => a + b, 0) / this.heartbeatRtts.length 
      : null;
      
    return {
      status: this.ws?.readyState === WebSocket.OPEN ? 'connected' : 
              this.isConnecting ? 'connecting' : 'disconnected',
      lastHeartbeat: this.lastHeartbeatResponse,
      circuitStatus: this.circuitBreakerState,
      reconnectAttempts: this.reconnectAttempt,
      avgRtt
    };
  }
  
  // Send WebSocket message and wait for response
  private sendWithResponse(message: any, timeoutMs: number = 5000): Promise<any> {
    return new Promise((resolve, reject) => {
      // Generate a unique request ID
      const requestId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      
      // Add request ID to message
      const messageWithId = {
        ...message,
        requestId
      };
      
      // Set timeout for response
      const timeoutId = setTimeout(() => {
        this.pendingResponses.delete(requestId);
        reject(new Error(`Timeout waiting for response to ${message.type}`));
      }, timeoutMs);
      
      // Store promise resolvers
      this.pendingResponses.set(requestId, {
        resolve,
        reject,
        timeout: timeoutId as unknown as number
      });
      
      // Send the message
      if (!this.send(messageWithId)) {
        clearTimeout(timeoutId);
        this.pendingResponses.delete(requestId);
        reject(new Error('Failed to send message - connection not open'));
      }
    });
  }

  // Heartbeat management methods
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatTimer = window.setInterval(() => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        this.stopHeartbeat();
        return;
      }
      
      // Send heartbeat
      this.lastHeartbeatSent = Date.now();
      this.send({ 
        type: 'heartbeat', 
        timestamp: this.lastHeartbeatSent
      });
      
      // Set timeout for heartbeat response
      this.heartbeatTimeout = window.setTimeout(() => {
        console.warn('Heartbeat timeout - no response received');
        
        // Check how long since last heartbeat response
        const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeatResponse;
        
        if (timeSinceLastHeartbeat > this.heartbeatTimeoutMs * 2) {
          console.error('Connection seems dead, forcing reconnect');
          
          // Force reconnect
          if (this.ws) {
            this.ws.close(4000, 'Heartbeat timeout');
            this.ws = null;
          }
          
          this.attemptReconnect();
        }
      }, this.heartbeatTimeoutMs);
    }, this.heartbeatInterval);
  }
  
  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    
    if (this.heartbeatTimeout !== null) {
      clearTimeout(this.heartbeatTimeout);
      this.heartbeatTimeout = null;
    }
  }
  
  private stopReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
  
  private updateHeartbeatRtts(rtt: number): void {
    this.heartbeatRtts.push(rtt);
    
    // Keep only the most recent N readings
    if (this.heartbeatRtts.length > this.connectionQualityBufferSize) {
      this.heartbeatRtts.shift();
    }
    
    this.updateConnectionQuality();
  }
  
  private updateConnectionQuality(): void {
    if (this.heartbeatRtts.length < 3) {
      return; // Not enough data yet
    }
    
    // Calculate average RTT
    const avgRtt = this.heartbeatRtts.reduce((a, b) => a + b, 0) / this.heartbeatRtts.length;
    
    // Determine quality
    let quality: ConnectionQuality;
    if (avgRtt < 100) {
      quality = 'good';
    } else if (avgRtt < 300) {
      quality = 'degraded';
    } else {
      quality = 'poor';
    }
    
    this.emit('connection_quality', { quality, avgRtt });
  }
  
  private notifyConnectionIssue(severity: 'warning' | 'critical'): void {
    if (severity === 'critical') {
      this.emit('critical_connection_issue', {
        message: 'Lost connection to trading server',
        reconnectAttempt: this.reconnectAttempt,
        maxAttempts: this.maxReconnectAttempts
      });
    } else {
      this.emit('connection_warning', {
        message: 'Connection issues detected',
        reconnectAttempt: this.reconnectAttempt
      });
    }
  }
  
  private clearPendingResponses(): void {
    // Clear all pending response timeouts
    for (const { timeout } of this.pendingResponses.values()) {
      clearTimeout(timeout);
    }
    
    this.pendingResponses.clear();
  }
  
  public resetCircuitBreaker(): void {
    this.circuitBreakerState = 'CLOSED';
    this.consecutiveFailures = 0;
    this.emit('circuit_reset', { message: 'Circuit breaker manually reset' });
  }
  
  public dispose(): void {
    this.disconnect();
    this.removeAllListeners();
  }
}