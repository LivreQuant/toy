// src/services/websocket/ws-client.ts
import { TokenManager } from '../auth/token-manager';
import { BackoffStrategy } from './backoff-strategy';

export interface WebSocketMessage {
  type: string;
  data?: any;
}

export interface WebSocketClientOptions {
  reconnectMaxAttempts?: number;
  initialReconnectDelayMs?: number;
  maxReconnectDelayMs?: number;
  heartbeatIntervalMs?: number;
  heartbeatTimeoutMs?: number;
}

export class WebSocketClient {
  private url: string;
  private tokenManager: TokenManager;
  private socket: WebSocket | null = null;
  private isConnecting: boolean = false;
  private backoffStrategy: BackoffStrategy;
  private sessionId: string | null = null;
  private eventHandlers: Map<string, Set<Function>> = new Map();
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private heartbeatTimeoutTimer: number | null = null;
  private reconnectAttempt: number = 0;
  private maxReconnectAttempts: number;
  private heartbeatInterval: number;
  private heartbeatTimeout: number;
  private lastMessageTime: number = 0;
  
  constructor(url: string, tokenManager: TokenManager, options: WebSocketClientOptions = {}) {
    this.url = url;
    this.tokenManager = tokenManager;
    this.backoffStrategy = new BackoffStrategy(
      options.initialReconnectDelayMs || 1000,
      options.maxReconnectDelayMs || 30000
    );
    this.maxReconnectAttempts = options.reconnectMaxAttempts || 10;
    this.heartbeatInterval = options.heartbeatIntervalMs || 30000; // 30 seconds
    this.heartbeatTimeout = options.heartbeatTimeoutMs || 5000; // 5 seconds
  }
  
  public async connect(sessionId: string): Promise<boolean> {
    if (this.socket?.readyState === WebSocket.OPEN) {
      return true;
    }
    
    if (this.isConnecting) {
      return new Promise<boolean>(resolve => {
        this.once('connected', () => resolve(true));
        this.once('connection_failed', () => resolve(false));
      });
    }
    
    this.isConnecting = true;
    this.sessionId = sessionId;
    
    try {
      // Get auth token
      const token = await this.tokenManager.getAccessToken();
      if (!token) {
        this.isConnecting = false;
        this.emit('error', { error: 'No valid authentication token' });
        return false;
      }
      
      // Build WebSocket URL with query parameters
      const wsUrl = `${this.url}?token=${encodeURIComponent(token)}&sessionId=${encodeURIComponent(sessionId)}`;
      
      // Create WebSocket
      this.socket = new WebSocket(wsUrl);
      
      return new Promise<boolean>((resolve) => {
        if (!this.socket) {
          this.isConnecting = false;
          resolve(false);
          return;
        }
        
        this.socket.onopen = () => {
          this.isConnecting = false;
          this.reconnectAttempt = 0;
          this.backoffStrategy.reset();
          this.lastMessageTime = Date.now();
          
          this.emit('connected', { connected: true });
          this.startHeartbeat();
          
          resolve(true);
        };
        
        this.socket.onmessage = (event) => {
          this.handleMessage(event);
        };
        
        this.socket.onclose = (event) => {
          this.handleClose(event);
          
          if (this.isConnecting) {
            this.isConnecting = false;
            resolve(false);
          }
        };
        
        this.socket.onerror = (event) => {
          console.error('WebSocket error:', event);
          this.emit('error', { error: event });
          
          if (this.isConnecting) {
            this.isConnecting = false;
            resolve(false);
          }
        };
      });
    } catch (error) {
      this.isConnecting = false;
      this.emit('error', { error });
      return false;
    }
  }
  
  public disconnect(): void {
    this.stopHeartbeat();
    this.stopReconnectTimer();
    
    if (this.socket) {
      try {
        this.socket.close(1000, 'Client disconnecting');
      } catch (error) {
        console.error('Error closing WebSocket:', error);
      }
      this.socket = null;
    }
    
    this.emit('disconnected', { reason: 'client_disconnect' });
  }
  
  public send(message: WebSocketMessage | string): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return false;
    }
    
    try {
      const data = typeof message === 'string' ? message : JSON.stringify(message);
      this.socket.send(data);
      return true;
    } catch (error) {
      console.error('Error sending WebSocket message:', error);
      this.emit('error', { error });
      return false;
    }
  }
  
  public on(event: string, callback: Function): void {
    if (!this.eventHandlers.has(event)) {
      this.eventHandlers.set(event, new Set());
    }
    
    this.eventHandlers.get(event)?.add(callback);
  }
  
  public off(event: string, callback: Function): void {
    const handlers = this.eventHandlers.get(event);
    if (handlers) {
      handlers.delete(callback);
    }
  }
  
  public once(event: string, callback: Function): void {
    const onceCallback = (...args: any[]) => {
      this.off(event, onceCallback);
      callback(...args);
    };
    
    this.on(event, onceCallback);
  }
  
  private emit(event: string, data: any): void {
    const handlers = this.eventHandlers.get(event);
    if (handlers) {
      handlers.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in WebSocket event handler for ${event}:`, error);
        }
      });
    }
    
    // Also emit to wildcard listeners
    const wildcardHandlers = this.eventHandlers.get('*');
    if (wildcardHandlers) {
      wildcardHandlers.forEach(callback => {
        try {
          callback(event, data);
        } catch (error) {
          console.error(`Error in WebSocket wildcard event handler for ${event}:`, error);
        }
      });
    }
  }
  
  private handleMessage(event: MessageEvent): void {
    // Update last message time
    this.lastMessageTime = Date.now();
    
    // Reset heartbeat timeout if active
    if (this.heartbeatTimeoutTimer !== null) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
    
    try {
      // Parse message if it's JSON
      let message: any;
      
      if (typeof event.data === 'string') {
        try {
          message = JSON.parse(event.data);
        } catch {
          // Not JSON, use as is
          message = event.data;
        }
      } else {
        message = event.data;
      }
      
      // Handle message based on type if available
      if (message && typeof message === 'object' && message.type) {
        this.emit(message.type, message.data || message);
        
        // Special handling for heartbeat
        if (message.type === 'heartbeat') {
          this.emit('heartbeat', {
            timestamp: message.timestamp || Date.now()
          });
        }
      }
      
      // Always emit generic message event
      this.emit('message', message);
    } catch (error) {
      console.error('Error handling WebSocket message:', error);
      this.emit('error', { error });
    }
  }
  
  private handleClose(event: CloseEvent): void {
    this.stopHeartbeat();
    
    const wasClean = event.wasClean;
    const code = event.code;
    const reason = event.reason || 'Unknown reason';
    
    console.log(`WebSocket closed: ${reason} (${code})`);
    
    this.emit('disconnected', {
      wasClean,
      code,
      reason
    });
    
    this.socket = null;
    
    // Don't reconnect on clean closure with normal code
    if (wasClean && code === 1000) {
      return;
    }
    
    // Attempt to reconnect
    this.attemptReconnect();
  }
  
  private attemptReconnect(): void {
    if (this.reconnectTimer !== null) {
      return; // Already attempting to reconnect
    }
    
    if (!this.sessionId) {
      this.emit('error', { error: 'Cannot reconnect without session ID' });
      return;
    }
    
    if (this.reconnectAttempt >= this.maxReconnectAttempts) {
      this.emit('max_reconnect_attempts', {
        attempts: this.reconnectAttempt,
        maxAttempts: this.maxReconnectAttempts
      });
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
      
      const connected = await this.connect(this.sessionId!);
      
      if (!connected && this.reconnectAttempt < this.maxReconnectAttempts) {
        // If connection failed, try again
        this.attemptReconnect();
      }
    }, delay);
  }
  
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    // Start heartbeat interval
    this.heartbeatTimer = window.setInterval(() => {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        this.stopHeartbeat();
        return;
      }
      
      // Send heartbeat
      this.send({
        type: 'heartbeat',
        data: {
          timestamp: Date.now()
        }
      });
      
      // Set timeout for heartbeat response
      this.heartbeatTimeoutTimer = window.setTimeout(() => {
        const elapsed = Date.now() - this.lastMessageTime;
        
        if (elapsed > this.heartbeatTimeout * 2) {
          console.warn(`No heartbeat response for ${elapsed}ms, connection may be dead`);
          
          // Force reconnect
          if (this.socket) {
            this.socket.close(4000, 'Heartbeat timeout');
            this.socket = null;
          }
          
          this.attemptReconnect();
        }
      }, this.heartbeatTimeout);
    }, this.heartbeatInterval);
  }
  
  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    
    if (this.heartbeatTimeoutTimer !== null) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }
  
  private stopReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
  
  public isConnected(): boolean {
    return this.socket !== null && this.socket.readyState === WebSocket.OPEN;
  }
}