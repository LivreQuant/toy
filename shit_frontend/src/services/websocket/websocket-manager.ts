// src/services/websocket/websocket-manager.ts
import { TokenManager } from '../auth/token-manager';
import { WebSocketOptions } from './types';
import { DeviceIdManager } from '../../utils/device-id-manager';
import { Disposable } from '../../utils/disposable';
import { config } from '../../config';
import { AppErrorHandler } from '../../utils/app-error-handler';
import { TypedEventEmitter } from '../utils/typed-event-emitter';
import { getLogger } from '../../boot/logging';
import { filter, map } from 'rxjs/operators';
import { BehaviorSubject, Observable } from 'rxjs';

import { 
  WebSocketMessage, 
  HeartbeatMessage,
  isHeartbeatMessage,
  isExchangeDataMessage,
  isOrderUpdateMessage,
  isResponseMessage
} from './message-types';

import { 
  ConnectionServiceType, 
  ConnectionStatus, 
  UnifiedConnectionState 
} from '../connection/unified-connection-state';

// Define all WebSocket event types
export interface WebSocketEvents {
  connected: void;
  disconnected: { code?: number; reason?: string; wasClean?: boolean };
  message: any;
  heartbeat: {
    timestamp: number;
    latency: number;
    simulatorStatus?: string;
    deviceId?: string;
  };
  message_error: {
    error: Error;
    rawData: any;
  };
  exchange_data: Record<string, any>;
  portfolio_data: {
    positions: Record<string, any>;
    cash: number;
    timestamp: number;
  };
  risk_data: Record<string, any>;
  order_update: {
    orderId: string;
    symbol: string;
    status: string;
    filledQty: number;
    remainingQty: number;
    price?: number;
    timestamp: number;
  };
  session_ready_response: any;
  session_invalidated: { reason: string };
}

export class WebSocketManager extends TypedEventEmitter<WebSocketEvents> implements Disposable {
  private logger = getLogger('WebSocketManager');
  private tokenManager: TokenManager;
  private unifiedState: UnifiedConnectionState;
  private webSocket: WebSocket | null = null;
  private heartbeatManager: HeartbeatManager | null = null;
  private isDisposed: boolean = false;
  private pendingResponses: Map<string, { 
    resolve: Function, 
    reject: Function, 
    timeoutId: number 
  }> = new Map();
  private options: WebSocketOptions;
  
  // RxJS subjects for reactive state
  private connectionStatus$ = new BehaviorSubject<ConnectionStatus>(ConnectionStatus.DISCONNECTED);
  private latestMessage$ = new BehaviorSubject<WebSocketMessage | null>(null);
  
  constructor(
    tokenManager: TokenManager,
    unifiedState: UnifiedConnectionState,
    options: WebSocketOptions = {}
  ) {
    super('WebSocketManager');
    
    this.tokenManager = tokenManager;
    this.unifiedState = unifiedState;
    
    this.options = {
      heartbeatInterval: options.heartbeatInterval || 15000,
      heartbeatTimeout: options.heartbeatTimeout || 5000,
      preventAutoConnect: true // Always prevent auto-connect
    };
    
    this.logger.info('WebSocketManager initialized', { preventAutoConnect: this.options.preventAutoConnect });
  }
  
  /**
   * Returns an observable of the connection status
   */
  public getConnectionStatus(): Observable<ConnectionStatus> {
    return this.connectionStatus$.asObservable();
  }
  
  /**
   * Returns an observable for a specific message type
   */
  public getMessageObservable<T>(messageType: string): Observable<T> {
    return this.latestMessage$.pipe(
      filter(message => message !== null && message.type === messageType),
      map(message => message as unknown as T)
    );
  }
  
  /**
   * Establishes a WebSocket connection to the server
   */
  public async connect(): Promise<boolean> {
    return this.logger.trackTime('websocket-connect', async () => {
      if (this.isDisposed) {
        this.logger.error('Cannot connect: WebSocketManager is disposed');
        return false;
      }
      
      if (!this.tokenManager.isAuthenticated()) {
        this.logger.error('Cannot connect: Not authenticated');
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.DISCONNECTED,
          error: 'Authentication required'
        });
        this.connectionStatus$.next(ConnectionStatus.DISCONNECTED);
        return false;
      }
      
      // Check if already connected or connecting
      if (this.webSocket) {
        if (this.webSocket.readyState === WebSocket.CONNECTING) {
          this.logger.warn('Connection already in progress');
          return false;
        }
        
        if (this.webSocket.readyState === WebSocket.OPEN) {
          this.logger.warn('Already connected');
          return true;
        }
        
        // Close existing socket if it's in a closing or closed state
        this.disconnect('reconnecting');
      }
      
      try {
        this.logger.info('Initiating WebSocket connection');
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.CONNECTING,
          error: null
        });
        this.connectionStatus$.next(ConnectionStatus.CONNECTING);
        
        // Get authentication token
        const token = await this.tokenManager.getAccessToken();
        if (!token) {
          throw new Error('Failed to get authentication token');
        }
        
        // Get device ID
        const deviceId = DeviceIdManager.getInstance().getDeviceId();
        
        // Build connection URL with query parameters
        const params = new URLSearchParams({
          token,
          deviceId,
          userAgent: navigator.userAgent
        });
        
        const wsUrl = `${config.wsBaseUrl}?${params.toString()}`;
        
        // Create WebSocket instance
        this.webSocket = new WebSocket(wsUrl);
        
        // Return a promise that resolves when the connection is established or fails
        return new Promise<boolean>((resolve) => {
          if (!this.webSocket) {
            this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
              status: ConnectionStatus.DISCONNECTED,
              error: 'Failed to create WebSocket instance'
            });
            this.connectionStatus$.next(ConnectionStatus.DISCONNECTED);
            resolve(false);
            return;
          }
          
          // Setup event handlers
          this.webSocket.onopen = () => {
            this.handleConnectionOpen();
            resolve(true);
          };
          
          this.webSocket.onclose = (event) => {
            this.handleConnectionClose(event);
            // Only resolve with false if this was the initial connection attempt
            if (this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status === ConnectionStatus.CONNECTING) {
              resolve(false);
            }
          };
          
          this.webSocket.onerror = (event) => {
            this.handleConnectionError(event);
            // Only resolve with false if this was the initial connection attempt
            if (this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status === ConnectionStatus.CONNECTING) {
              resolve(false);
            }
          };
          
          this.webSocket.onmessage = this.handleMessage.bind(this);
        });
      } catch (error) {
        this.logger.error('Error initiating WebSocket connection', { error });
        
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.DISCONNECTED,
          error: error instanceof Error ? error.message : String(error)
        });
        this.connectionStatus$.next(ConnectionStatus.DISCONNECTED);
        
        AppErrorHandler.handleConnectionError(
          error instanceof Error ? error : new Error(String(error)),
          ErrorSeverity.HIGH,
          'WebSocketConnection'
        );
        
        return false;
      }
    });
  }
  
  /**
   * Handles successful WebSocket connection
   */
  private handleConnectionOpen(): void {
    if (this.isDisposed) return;
    
    this.logger.info('WebSocket connection established');
    
    // Start heartbeat manager
    this.heartbeatManager = new HeartbeatManager({
      ws: this.webSocket!,
      eventEmitter: this,
      options: {
        interval: this.options.heartbeatInterval,
        timeout: this.options.heartbeatTimeout
      }
    });
    
    this.heartbeatManager.start();
    
    // Update connection state
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
      status: ConnectionStatus.CONNECTED,
      lastConnected: Date.now(),
      error: null,
      recoveryAttempts: 0
    });
    this.connectionStatus$.next(ConnectionStatus.CONNECTED);
    
    // Emit connected event
    this.emit('connected', undefined);
  }
  
  /**
   * Handles WebSocket connection closure
   */
  private handleConnectionClose(event: CloseEvent): void {
    if (this.isDisposed) return;
    
    this.logger.warn(`WebSocket connection closed. Code: ${event.code}, Reason: "${event.reason}", Clean: ${event.wasClean}`);
    
    // Stop heartbeat manager
    if (this.heartbeatManager) {
      this.heartbeatManager.stop();
      this.heartbeatManager = null;
    }
    
    // Update connection state
    this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
      status: ConnectionStatus.DISCONNECTED,
      error: event.reason || `Connection closed (Code: ${event.code})`,
      recoveryAttempts: this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).recoveryAttempts
    });
    this.connectionStatus$.next(ConnectionStatus.DISCONNECTED);
    
    // Clear pending responses
    this.clearPendingResponses(`connection_closed_${event.code}`);
    
    // Clear socket reference
    this.webSocket = null;
    
    // Emit disconnected event
    this.emit('disconnected', {
      code: event.code,
      reason: event.reason,
      wasClean: event.wasClean
    });
  }
  
  /**
   * Handles WebSocket connection errors
   */
  private handleConnectionError(event: Event): void {
    if (this.isDisposed) return;
    
    this.logger.error('WebSocket connection error', { event });
    
    AppErrorHandler.handleConnectionError(
      'WebSocket connection error',
      ErrorSeverity.MEDIUM,
      'WebSocketManager'
    );
    
    // Note: Usually the onclose handler will be called after this
  }
  
  /**
   * Processes incoming WebSocket messages
   */
  private handleMessage(event: MessageEvent): void {
    if (this.isDisposed) return;
    
    try {
      const message = JSON.parse(event.data) as WebSocketMessage;
      
      // Update latest message subject
      this.latestMessage$.next(message);
      
      // Emit for all message types
      this.emit('message', message);
      
      // Handle message based on type
      if (isHeartbeatMessage(message)) {
        this.handleHeartbeatMessage(message);
      } else if (isResponseMessage(message)) {
        this.handleResponseMessage(message);
      } else {
        // Handle various data message types with type safety
        if (isExchangeDataMessage(message)) {
          this.emit('exchange_data', message.data);
        } else if (isOrderUpdateMessage(message)) {
          this.emit('order_update', message.data);
        } else if (message.type === 'session_invalidated') {
          this.emit('session_invalidated', { 
            reason: 'session_invalidated' in message ? message.reason : 'Unknown reason' 
          });
        } else if (message.type === 'session_ready_response') {
          this.emit('session_ready_response', message);
        }
      }
    } catch (error) {
      this.logger.error('Error processing WebSocket message', { 
        error, 
        data: typeof event.data === 'string' ? event.data.substring(0, 200) : 'Non-string data' 
      });
      
      this.emit('message_error', {
        error: error instanceof Error ? error : new Error(String(error)),
        rawData: event.data
      });
    }
  }
  
  /**
   * Handles heartbeat messages from the server
   */
  private handleHeartbeatMessage(message: HeartbeatMessage): void {
    if (this.isDisposed) return;
    
    // Notify heartbeat manager
    this.heartbeatManager?.handleHeartbeatResponse();
    
    // Update unified state with heartbeat data
    const now = Date.now();
    const latency = message.timestamp ? (now - message.timestamp) : -1;
    
    this.unifiedState.updateHeartbeat(now, latency);
    
    if (message.simulatorStatus) {
      this.unifiedState.updateSimulatorStatus(message.simulatorStatus);
    }
    
    // Emit heartbeat event
    this.emit('heartbeat', {
      timestamp: message.timestamp,
      latency,
      simulatorStatus: message.simulatorStatus,
      deviceId: message.deviceId
    });
  }
  
  /**
   * Handles response messages from the server
   */
  private handleResponseMessage(message: WebSocketMessage & { requestId: string }): void {
    if (this.isDisposed) return;
    
    const { requestId } = message;
    const pending = this.pendingResponses.get(requestId);
    
    if (pending) {
      this.logger.debug(`Received response for request ${requestId}`);
      clearTimeout(pending.timeoutId);
      
      if ('error' in message && message.error) {
        pending.reject(new Error(message.error.message || 'Request failed'));
      } else {
        pending.resolve(message);
      }
      
      this.pendingResponses.delete(requestId);
    } else {
      this.logger.warn(`Received response for unknown request ID: ${requestId}`);
    }
  }
  
  /**
   * Disconnects the WebSocket connection
   */
  public disconnect(reason: string = 'client_disconnect'): void {
    if (this.isDisposed && reason !== 'disposing') {
      this.logger.info(`Disconnect called on disposed WebSocketManager. Reason: ${reason}`);
      return;
    }
    
    this.logger.warn(`Disconnecting WebSocket. Reason: ${reason}`);
    
    // Stop heartbeat manager
    if (this.heartbeatManager) {
      this.heartbeatManager.stop();
      this.heartbeatManager = null;
    }
    
    // Close WebSocket if open
    if (this.webSocket) {
      // Remove event listeners
      this.webSocket.onopen = null;
      this.webSocket.onclose = null;
      this.webSocket.onerror = null;
      this.webSocket.onmessage = null;
      
      // Only close if not already closed
      if (this.webSocket.readyState === WebSocket.OPEN || this.webSocket.readyState === WebSocket.CONNECTING) {
        try {
          this.webSocket.close(1000, reason);
        } catch (error) {
          this.logger.error('Error closing WebSocket', { error });
        }
      }
      
      this.webSocket = null;
    }
    
    // Clear pending responses
    this.clearPendingResponses(reason);
    
    // Update state if not disposed
    if (!this.isDisposed) {
      const currentState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
      if (currentState.status !== ConnectionStatus.DISCONNECTED) {
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, {
          status: ConnectionStatus.DISCONNECTED,
          error: `Disconnected: ${reason}`,
          lastConnected: currentState.lastConnected,
          recoveryAttempts: currentState.recoveryAttempts
        });
        this.connectionStatus$.next(ConnectionStatus.DISCONNECTED);
      }
    }
  }
  
  /**
   * Sends a message through the WebSocket connection
   */
  public send(message: any): void {
    if (this.isDisposed) {
      throw new Error('Cannot send message: WebSocketManager is disposed');
    }
    
    if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
      throw new Error('Cannot send message: WebSocket is not open');
    }
    
    try {
      this.webSocket.send(JSON.stringify(message));
    } catch (error) {
      this.logger.error('Error sending WebSocket message', { error });
      throw new Error(`Failed to send WebSocket message: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  
  /**
   * Sends a message and waits for a response
   */
  public sendWithResponse<T = any>(message: any, timeoutMs: number = 5000): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      try {
        // Generate unique request ID if not provided
        const requestId = message.requestId || `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
        const messageWithId = { ...message, requestId };
        
        // Set up timeout to reject if no response received
        const timeoutId = window.setTimeout(() => {
          if (this.pendingResponses.has(requestId)) {
            this.logger.warn(`Request timed out for requestId: ${requestId}`);
            this.pendingResponses.delete(requestId);
            reject(new Error(`Request timeout for type ${message.type} (ID: ${requestId})`));
          }
        }, timeoutMs);
        
        // Store resolve and reject functions for when response arrives
        this.pendingResponses.set(requestId, { resolve, reject, timeoutId });
        
        // Send the message
        this.send(messageWithId);
      } catch (error) {
        reject(error);
      }
    });
  }
  
  /**
   * Clears all pending response handlers
   */
  private clearPendingResponses(reason: string): void {
    if (this.pendingResponses.size === 0) return;
    
    this.logger.warn(`Clearing ${this.pendingResponses.size} pending responses. Reason: ${reason}`);
    
    this.pendingResponses.forEach((pending, requestId) => {
      clearTimeout(pending.timeoutId);
      pending.reject(new Error(`Request cancelled: ${reason} (ID: ${requestId})`));
    });
    
    this.pendingResponses.clear();
  }
  
  /**
   * Returns whether the WebSocket is currently connected
   */
  public isConnected(): boolean {
    return this.webSocket !== null && this.webSocket.readyState === WebSocket.OPEN;
  }
  
  /**
   * Cleans up resources when the manager is no longer needed
   */
  public dispose(): void {
    if (this.isDisposed) {
      this.logger.warn('WebSocketManager already disposed');
      return;
    }
    
    this.logger.warn('Disposing WebSocketManager');
    this.isDisposed = true;
    
    // Disconnect WebSocket
    this.disconnect('disposing');
    
    // Complete RxJS subjects
    this.connectionStatus$.complete();
    this.latestMessage$.complete();
    
    // Call parent dispose to clean up event listeners
    super.dispose();
    
    this.logger.info('WebSocketManager disposed');
  }
  
  /**
   * Implements the Symbol.dispose method for the Disposable interface
   */
  [Symbol.dispose](): void {
    this.dispose();
  }
}