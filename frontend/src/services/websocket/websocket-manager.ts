// src/services/websocket/websocket-manager.ts
import { BehaviorSubject, Observable, Subscription } from 'rxjs';
import { filter, map } from 'rxjs/operators';
import { TokenManager } from '../auth/token-manager';
import { WebSocketOptions } from './types';
import { DeviceIdManager } from '../auth/device-id-manager';
import { Disposable } from '../../utils/disposable';
import { config } from '../../config';
import { AppErrorHandler } from '../../utils/app-error-handler';
import { ErrorSeverity } from '../../utils/error-handler';
import { TypedEventEmitter } from '../../utils/typed-event-emitter';
import { EnhancedLogger } from '../../utils/enhanced-logger';
import { getLogger } from '../../boot/logging';
import {
  WebSocketMessage,
  ClientHeartbeatMessage,
  ClientReconnectMessage,
  ServerHeartbeatAckMessage,
  ServerReconnectResultMessage,
  ServerExchangeDataStatusMessage,
  isServerHeartbeatAckMessage,
  isServerReconnectResultMessage,
  isServerExchangeDataStatusMessage,
  isServerConnectionReplacedMessage,
  ClientSubmitOrderMessage,
  ClientCancelOrderMessage,
  ClientStartSimulatorMessage,
  ClientStopSimulatorMessage,
  ClientSessionInfoRequest,
  ClientStopSessionRequest,
  ServerSessionInfoResponse,
  ServerStopSessionResponse,
  ServerSimulatorStartedResponse,
  ServerSimulatorStoppedResponse,
  ServerOrderSubmittedResponse,
  ServerOrderCancelledResponse,
  ServerConnectionReplacedMessage,
  DeviceIdInvalidatedMessage,

  isServerSimulatorStatusUpdateMessage,
  ServerSimulatorStatusUpdateMessage,

} from './message-types';
import {
  appState,
  ConnectionStatus,
  ConnectionQuality
} from '../state/app-state.service';
import { HeartbeatManager } from './heartbeat-manager';

// Define WebSocket specific event types
export interface WebSocketEvents {
  message: WebSocketMessage;
  heartbeat_ack: ServerHeartbeatAckMessage;
  reconnect_result: ServerReconnectResultMessage;
  exchange_data_status: ServerExchangeDataStatusMessage;
  message_error: { error: Error; rawData: any };
  session_info: ServerSessionInfoResponse;
  session_stopped: ServerStopSessionResponse;
  simulator_started: ServerSimulatorStartedResponse;
  simulator_stopped: ServerSimulatorStoppedResponse;
  order_submitted: ServerOrderSubmittedResponse;
  order_cancelled: ServerOrderCancelledResponse;
  connection_replaced: ServerConnectionReplacedMessage;
  device_id_invalidated: {
    deviceId: string, 
    reason?: string,
    currentValidDeviceId?: string // Add this property
  };
}

// Structure for pending request promises
interface PendingResponse {
  resolve: (value: any) => void;
  reject: (reason?: any) => void;
  timeoutId: number;
  requestId: string;
  requestTime: number;
}

export class WebSocketManager extends TypedEventEmitter<WebSocketEvents> implements Disposable {
  // Note: Inherits 'protected logger: EnhancedLogger' from base class
  private tokenManager: TokenManager;
  private webSocket: WebSocket | null = null;
  private heartbeatManager: HeartbeatManager | null = null;
  private pendingResponses: Map<string, PendingResponse> = new Map();
  private options: Required<WebSocketOptions>;
  private connectionStatus$ = new BehaviorSubject<ConnectionStatus>(ConnectionStatus.DISCONNECTED);
  private subscriptions = new Subscription();
  private readonly responseTimeoutMs = 15000;

  constructor(
    tokenManager: TokenManager,
    options: WebSocketOptions = {}
  ) {
    // Create logger instance first
    const loggerInstance = getLogger('WebSocketManager');
    // Pass logger instance to super()
    super(loggerInstance);

    this.tokenManager = tokenManager;
    const defaultOptions: Required<WebSocketOptions> = {
        heartbeatInterval: 30000,
        heartbeatTimeout: 10000,
        reconnectMaxAttempts: 5,
        preventAutoConnect: true
    };
    this.options = { ...defaultOptions, ...options };
    this.connectionStatus$.next(appState.getState().connection.webSocketStatus);
    this.logger.info('WebSocketManager initialized', { options: this.options });
  }

  public getConnectionStatus(): Observable<ConnectionStatus> {
    return this.connectionStatus$.asObservable();
  }

  public async connect(): Promise<boolean> {
    if (this.isDisposed) return false;

    // Add more detailed logging
    this.logger.info('WebSocketManager.connect() called - detailed debug info:');
    this.logger.info(`- Is authenticated: ${this.tokenManager.isAuthenticated()}`);
    
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.error('Cannot connect: Not authenticated');
      appState.updateConnectionState({
        webSocketStatus: ConnectionStatus.DISCONNECTED,
        lastConnectionError: 'Authentication required before connecting WebSocket'
      });
      this.connectionStatus$.next(ConnectionStatus.DISCONNECTED);
      return false;
    }

    const currentStatus = this.connectionStatus$.getValue();
    if (currentStatus === ConnectionStatus.CONNECTING || currentStatus === ConnectionStatus.CONNECTED) {
        this.logger.warn(`Connect call ignored: WebSocket status is already ${currentStatus}`);
        return currentStatus === ConnectionStatus.CONNECTED;
    }

    if (this.webSocket) {
      this.logger.warn('Connect called with existing socket, cleaning up previous instance.');
      this.cleanupWebSocket();
    }

    try {
      this.logger.info('Initiating WebSocket connection...');
      appState.updateConnectionState({ webSocketStatus: ConnectionStatus.CONNECTING, lastConnectionError: null });
      this.connectionStatus$.next(ConnectionStatus.CONNECTING);

      const token = await this.tokenManager.getAccessToken();
      this.logger.debug(`Token retrieved - length: ${token ? token.length : 0}, first 10 chars: ${token ? token.substring(0, 10) : 'null'}`);
      
      if (!token) throw new Error('Failed to get authentication token for WebSocket');

      const deviceId = DeviceIdManager.getInstance().getDeviceId();
      this.logger.debug(`Device ID: ${deviceId}`);
      
      const params = new URLSearchParams({ token, deviceId });
      const wsUrl = `${config.wsBaseUrl}?${params.toString()}`;

      this.logger.info(`Full WebSocket URL: ${wsUrl}`);
      this.logger.info(`WebSocket base URL from config: ${config.wsBaseUrl}`); 

      this.webSocket = new WebSocket(wsUrl);

      return new Promise<boolean>((resolve) => {
        if (!this.webSocket) {
            this.logger.error("WebSocket instance unexpectedly null after creation.");
            this.updateStateOnError('Failed to create WebSocket instance');
            resolve(false);
            return;
        }
        const ws = this.webSocket;
        const openHandler = () => {
            this.logger.info("WebSocket onopen event.");
            if (ws === this.webSocket) { this.handleConnectionOpen(); resolve(true); }
            else { this.logger.warn("onopen event for outdated WebSocket."); }
            cleanup();
        };
        const closeHandler = (event: CloseEvent) => {
            this.logger.warn(`WebSocket onclose event. Code: ${event.code}, Reason: "${event.reason}"`);
            if (ws === this.webSocket) {
                this.handleConnectionClose(event);
                if (this.connectionStatus$.getValue() === ConnectionStatus.CONNECTING) resolve(false);
            } else { this.logger.warn("onclose event for outdated WebSocket."); }
            cleanup();
        };
        const errorHandler = (event: Event) => {
            this.logger.error("WebSocket onerror event.", { event });
            if (ws === this.webSocket) {
               this.handleConnectionError(event);
               if (this.connectionStatus$.getValue() === ConnectionStatus.CONNECTING) resolve(false);
            } else { this.logger.warn("onerror event for outdated WebSocket."); }
            cleanup();
        };
        const cleanup = () => {
            if(ws) {
                ws.removeEventListener('open', openHandler);
                ws.removeEventListener('close', closeHandler);
                ws.removeEventListener('error', errorHandler);
            }
        };
        ws.addEventListener('open', openHandler);
        ws.addEventListener('close', closeHandler);
        ws.addEventListener('error', errorHandler);
        ws.addEventListener('message', this.handleMessage);
      });

    } catch (error: any) {
      this.logger.error('Error initiating WebSocket connection', { error: error.message });
      this.updateStateOnError(error instanceof Error ? error.message : String(error));
      AppErrorHandler.handleConnectionError(error, ErrorSeverity.HIGH, 'WebSocketConnectInitiation');
      return false;
    }
  }

  public disconnect(reason: string = 'manual'): void {
    this.logger.warn(`Disconnect requested. Reason: ${reason}`);
    if (this.webSocket) {
      const event = new CloseEvent('close', { code: 1000, reason: reason, wasClean: true });
      this.handleConnectionClose(event);
    } else {
      this.logger.info('Disconnect called but no active WebSocket connection.');
      if (this.connectionStatus$.getValue() !== ConnectionStatus.DISCONNECTED) {
          this.updateStateOnError(`Disconnected: ${reason}`);
      }
    }
  }

  private handleMessage = (event: MessageEvent): void => {
    if (this.isDisposed || event.currentTarget !== this.webSocket) return;
  
    try {
      const message = JSON.parse(event.data) as WebSocketMessage;
      this.logger.warn('FULL WebSocket Message Received', { 
        type: message.type, 
        fullMessage: message 
      });
  
      // Specifically for session_info
      if (message.type === 'session_info') {
        this.logger.warn('Session Info Received', {
          sessionId: (message as ServerSessionInfoResponse).sessionId,
          success: (message as ServerSessionInfoResponse).success
        });
      }
        
      // Add a check for device ID invalidation message
      if (message.type === 'device_id_invalidated') {
        this.handleDeviceIdInvalidatedMessage(message as DeviceIdInvalidatedMessage);
        this.emit('device_id_invalidated', message);
        return;
      }

      // Emit generic message event
      this.emit('message', message);
  
      // Handle specific message types
      if (isServerHeartbeatAckMessage(message)) {
        this.handleHeartbeatAckMessage(message);
      } else if (isServerSimulatorStatusUpdateMessage(message)) {
        this.handleSimulatorStatusUpdateMessage(message);
      } else if (isServerReconnectResultMessage(message)) {
        this.handleReconnectResultMessage(message);
      } else if (isServerExchangeDataStatusMessage(message)) {
        this.handleExchangeDataStatusMessage(message);
      } else if (isServerConnectionReplacedMessage(message)) {
        this.handleConnectionReplacedMessage(message);
        this.emit('connection_replaced', message);
      } else {
        // For other message types we're not specifically handling
        this.logger.debug(`Received message of type: ${message.type}`);
      }
  
      // Check for pending response handlers
      if ('requestId' in message && message.requestId) {  // Add null check here
        const pendingReq = this.pendingResponses.get(message.requestId);
        if (pendingReq) {
          clearTimeout(pendingReq.timeoutId);
          pendingReq.resolve(message);
          this.pendingResponses.delete(message.requestId);
          this.logger.debug(`Resolved pending request: ${message.requestId}`);
        }
      }
    } catch (error: any) {
      this.logger.error('Error processing WebSocket message', { 
        error: error.message, 
        rawData: event.data?.substring(0, 200) 
      });
      this.emit('message_error', { error: error, rawData: event.data });
    }
  };

  private handleConnectionOpen(): void {
    if (this.isDisposed) return;
    console.log("CRITICAL DEBUG: WebSocket connection established successfully");
    this.logger.info('WebSocket connection established');
    appState.updateConnectionState({
        webSocketStatus: ConnectionStatus.CONNECTED,
        lastConnectionError: null,
    });
    this.connectionStatus$.next(ConnectionStatus.CONNECTED);

    // Add more detailed logging here
    console.log("CRITICAL DEBUG: App state after WebSocket connection:", {
      appConnectionState: appState.getState().connection,
      connectionStatus: this.connectionStatus$.getValue()
    });

    if (!this.heartbeatManager && this.webSocket) {
        this.heartbeatManager = new HeartbeatManager(
          this,
          {
            interval: this.options.heartbeatInterval,
            timeout: this.options.heartbeatTimeout
          }
        );
        this.heartbeatManager.start();
    }
  }

  // Add a new method to handle device ID invalidation
  private handleDeviceIdInvalidatedMessage(message: DeviceIdInvalidatedMessage): void {
    if (this.isDisposed) return;
    
    this.logger.warn(`Device ID invalidated: ${message.deviceId}. Reason: ${message.reason || 'unknown'}`);
    
    // Notify observers - use properties that match the interface
    this.emit('device_id_invalidated', {
      deviceId: DeviceIdManager.getInstance().getDeviceId(),
      reason: message.reason
    });
    
    // Disconnect WebSocket
    this.disconnect('device_id_invalidated');
  }

  private handleConnectionClose(event: CloseEvent): void {
    console.error('🔌 WebSocket Close Event DETAILS', {
      closeCode: event.code,
      closeReason: event.reason,
      wasClean: event.wasClean,
      currentStatus: this.connectionStatus$.getValue(),
      stackTrace: new Error().stack?.split('\n').slice(1, 10).join('\n'),
      timestamp: new Date().toISOString()
    });

    if (this.isDisposed) return;
    
    // Add more detailed logging
    this.logger.warn(`WebSocket connection closed. Details:`, {
      code: event.code,
      reason: event.reason,
      wasClean: event.wasClean,
      currentStatus: this.connectionStatus$.getValue(),
      timestamp: new Date().toISOString()
    });

    if (this.heartbeatManager) {
      this.heartbeatManager.dispose();
      this.heartbeatManager = null;
    }

    const errorReason = event.reason || `Connection closed (Code: ${event.code}, Clean: ${event.wasClean})`;
    appState.updateConnectionState({
        webSocketStatus: ConnectionStatus.DISCONNECTED,
        lastConnectionError: errorReason,
        quality: ConnectionQuality.UNKNOWN,
        heartbeatLatency: null,
    });
    this.connectionStatus$.next(ConnectionStatus.DISCONNECTED);

    this.cleanupWebSocket();
    this.clearPendingResponses(`connection_closed_${event.code}`);
  }

  private handleConnectionError(event: Event): void {
    if (this.isDisposed) return;

    const wsUrl = this.webSocket?.url || 'unknown';
    this.logger.error('WebSocket connection error event occurred.', { 
      event, 
      url: wsUrl,
      readyState: this.webSocket ? this.webSocket.readyState : 'no_socket'
    });
    
    this.logger.error('WebSocket connection error event occurred.', { event });
    appState.updateConnectionState({ lastConnectionError: 'WebSocket error occurred' });
    AppErrorHandler.handleConnectionError('WebSocket connection error', ErrorSeverity.MEDIUM, 'WebSocketManagerErrorEvent');
  }

  private handleConnectionReplacedMessage(message: any): void {
    if (this.isDisposed) return;
    
    this.logger.warn(`Connection replaced by another device: ${message.newDeviceId || 'unknown'}`);
    
    // Notify user via toast or other means
    AppErrorHandler.handleAuthError(
      'Your session was opened on another device. You have been logged out.',
      ErrorSeverity.MEDIUM,
      'ConnectionReplaced'
    );
    
    // Clean up the session locally
    this.disconnect('connection_replaced_by_other_device');
    
    // Clear auth tokens to force logout
    //this.tokenManager.clearTokens();
    
    // Update app state
    appState.updateAuthState({
      isAuthenticated: false,
      isAuthLoading: false,
      userId: null,
      lastAuthError: 'Session opened on another device'
    });
  }

  private updateStateOnError(errorMessage: string): void {
    appState.updateConnectionState({
        webSocketStatus: ConnectionStatus.DISCONNECTED,
        lastConnectionError: errorMessage,
        quality: ConnectionQuality.UNKNOWN,
        heartbeatLatency: null,
    });
    this.connectionStatus$.next(ConnectionStatus.DISCONNECTED);
    this.cleanupWebSocket();
  }

  private cleanupWebSocket(): void {
    if (this.webSocket) {
      this.logger.debug("Cleaning up WebSocket instance and listeners.");
      this.webSocket.removeEventListener('message', this.handleMessage);
      this.webSocket.onopen = null;
      this.webSocket.onclose = null;
      this.webSocket.onerror = null;
      if (this.webSocket.readyState === WebSocket.OPEN || this.webSocket.readyState === WebSocket.CONNECTING) {
        try { this.webSocket.close(1000, 'Client cleanup'); } catch (e) { this.logger.warn("Error closing WebSocket during cleanup:", e); }
      }
      this.webSocket = null;
    }
    if (this.heartbeatManager) {
      this.heartbeatManager.dispose();
      this.heartbeatManager = null;
    }
  }

  private handleHeartbeatAckMessage(message: ServerHeartbeatAckMessage): void {
    if (this.isDisposed) return;
      
    this.logger.debug('Detailed Heartbeat Ack Received', {
      deviceIdValid: message.deviceIdValid,
      sessionStatus: message.sessionStatus,
      simulatorStatus: message.simulatorStatus,
      clientTimestamp: message.clientTimestamp,
      serverTimestamp: Date.now(),
      latency: message.clientTimestamp ? (Date.now() - message.clientTimestamp) : -1
    });
      
    // Check for specific conditions that might trigger reconnection
    if (!message.deviceIdValid) {
      this.logger.error('Device ID invalidated - forcing reconnection');
    }

    if (message.sessionStatus !== 'valid') {
      this.logger.error(`Session status invalid: ${message.sessionStatus} - potential reconnection trigger`);
    }
    
    // Check if device ID is still valid
    if (!message.deviceIdValid) {
      this.logger.warn(`Device ID invalidated. Current valid device ID: ${message.deviceId}`);
      this.emit('device_id_invalidated', { 
        deviceId: DeviceIdManager.getInstance().getDeviceId(), 
        currentValidDeviceId: message.deviceId 
      });
      // You might want to trigger a disconnect or logout here
      this.disconnect('device_id_invalidated');
      return;
    }
    
    const now = Date.now();
    const latency = message.clientTimestamp ? (now - message.clientTimestamp) : -1;
    
    this.emit('heartbeat_ack', message);
      
    if (this.heartbeatManager) {
      this.heartbeatManager.handleHeartbeatResponse(message);
    }
    
    const quality = appState.calculateConnectionQuality(latency);
    appState.updateConnectionState({
      lastHeartbeatTime: now,
      heartbeatLatency: latency >= 0 ? latency : null,
      quality: quality,
      simulatorStatus: message.simulatorStatus
    });
  }

  // Add a new method to handle the simulator status update
  private handleSimulatorStatusUpdateMessage(message: ServerSimulatorStatusUpdateMessage): void {
    if (this.isDisposed) return;

    this.logger.info('Simulator Status Update Received', {
      simulatorId: message.simulatorId,
      status: message.simulatorStatus,
      timestamp: message.timestamp
    });

    // Update the app state with the new simulator status
    appState.updateConnectionState({
      simulatorStatus: message.simulatorStatus
    });
  }

  private handleReconnectResultMessage(message: ServerReconnectResultMessage): void {
    if (this.isDisposed) return;
    
    this.emit('reconnect_result', message);
    
    // Check if device ID is still valid
    if (!message.deviceIdValid) {
      this.logger.warn(`Device ID invalidated during reconnect. Current valid device ID: ${message.deviceId}`);
      this.emit('device_id_invalidated', { 
        deviceId: DeviceIdManager.getInstance().getDeviceId(), 
        currentValidDeviceId: message.deviceId 
      });
      this.disconnect('device_id_invalidated_reconnect');
      return;
    }
    
    if (message.success) {
      this.logger.info('Reconnection successful');
      appState.updateConnectionState({
        webSocketStatus: ConnectionStatus.CONNECTED,
        lastConnectionError: null,
        simulatorStatus: message.simulatorStatus
      });
    } else {
      this.logger.error(`Reconnection failed: ${message.message || 'Unknown error'}`);
      appState.updateConnectionState({
        webSocketStatus: ConnectionStatus.DISCONNECTED,
        lastConnectionError: message.message || 'Reconnection failed'
      });
    }
  }

  private handleExchangeDataStatusMessage(message: ServerExchangeDataStatusMessage): void {
    if (this.isDisposed) return;
    
    this.emit('exchange_data_status', message);
    
    // Convert the symbols format to match what appState expects
    if (message.symbols) {
      const convertedSymbols: Record<string, { price: number; open: number; high: number; low: number; close: number; volume: number; }> = {};
      
      Object.entries(message.symbols).forEach(([symbol, data]) => {
        convertedSymbols[symbol] = {
          price: data.price,
          open: data.price - (data.change || 0), // Approximate
          high: data.price, // Default/placeholder
          low: data.price, // Default/placeholder
          close: data.price, // Default/placeholder
          volume: data.volume || 0
        };
      });
      
      appState.updateExchangeSymbols(convertedSymbols);
    }
    
    // Update orders and positions if available
    if (message.userOrders || message.userPositions) {
      const portfolioUpdates: Partial<any> = {
        lastUpdated: message.timestamp
      };
      
      if (message.userOrders) {
        portfolioUpdates.orders = message.userOrders;
      }
      
      if (message.userPositions) {
        portfolioUpdates.positions = message.userPositions;
      }
      
      appState.updatePortfolioState(portfolioUpdates);
    }
  }

  private clearPendingResponses(reason: string): void {
    if (this.pendingResponses.size === 0) return;

    this.logger.warn(`Clearing ${this.pendingResponses.size} pending request(s) due to: ${reason}`);
    this.pendingResponses.forEach((pending, requestId) => {
        clearTimeout(pending.timeoutId);
        pending.reject(new Error(`Request cancelled: ${reason}`));
    });
    this.pendingResponses.clear();
  }

  // Add a method to send heartbeat
  public sendHeartbeat(): void {
    if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
      this.logger.debug('Cannot send heartbeat: WebSocket not open');
      return;
    }
    
    // Map the enum values to string values that match expected types
    const qualityMap: Record<ConnectionQuality, "good" | "degraded" | "poor"> = {
      [ConnectionQuality.GOOD]: "good",
      [ConnectionQuality.DEGRADED]: "degraded",
      [ConnectionQuality.POOR]: "poor",
      [ConnectionQuality.UNKNOWN]: "degraded" // Default fallback
    };
    
    // Map simulator status to expected values
    const mapSimulatorStatus = (status: string): "running" | "stopped" | "starting" | "stopping" => {
      if (status === "RUNNING") return "running";
      if (status === "STOPPED") return "stopped";
      if (status === "STARTING") return "starting";
      if (status === "STOPPING") return "stopping";
      return "stopped"; // Default fallback
    };
    
    const heartbeatMsg: ClientHeartbeatMessage = {
      type: 'heartbeat',
      timestamp: Date.now(),
      deviceId: DeviceIdManager.getInstance().getDeviceId(),
      connectionQuality: qualityMap[appState.getState().connection.quality] || "degraded",
      sessionStatus: 'active',
      simulatorStatus: mapSimulatorStatus(appState.getState().connection.simulatorStatus)
    };
    
    try {
      this.webSocket.send(JSON.stringify(heartbeatMsg));
      this.logger.debug('Heartbeat sent');
    } catch (error: any) {
      this.logger.error('Failed to send heartbeat', { error: error.message });
    }
  }

  // Add a method to send reconnect request
  public async sendReconnect(sessionToken?: string): Promise<boolean> {
    if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
      this.logger.error('Cannot send reconnect: WebSocket not open');
      return false;
    }
    
    const token = sessionToken || await this.tokenManager.getAccessToken();
    if (!token) {
      this.logger.error('Cannot reconnect: No valid session token');
      return false;
    }
    
    const requestId = `reconnect-${Date.now()}-${Math.random().toString(16).substring(2, 8)}`;
    
    const reconnectMsg: ClientReconnectMessage = {
      type: 'reconnect',
      deviceId: DeviceIdManager.getInstance().getDeviceId(),
      sessionToken: token,
      requestId
    };
    
    return new Promise<boolean>((resolve) => {
      // Listen for the reconnect result
      const subscription = this.once('reconnect_result', (result: ServerReconnectResultMessage) => {
        if (result.requestId === requestId) {
          resolve(result.success);
        } else {
          this.logger.warn('Received reconnect_result with mismatched requestId', { 
            expected: requestId, received: result.requestId 
          });
          resolve(false);
        }
      });
      
      // Set a timeout
      const timeoutId = window.setTimeout(() => {
        subscription.unsubscribe();
        this.logger.error('Reconnect request timed out');
        resolve(false);
      }, 10000);
      
      // Send the reconnect message
      try {
        if (!this.webSocket) {
          throw new Error("WebSocket is null");
        }
        this.webSocket.send(JSON.stringify(reconnectMsg));
        this.logger.info('Reconnect request sent', { requestId });
      } catch (error: any) {
        clearTimeout(timeoutId);
        subscription.unsubscribe();
        this.logger.error('Failed to send reconnect request', { error: error.message });
        resolve(false);
      }
    });
  }

  // Method to submit an order via WebSocket
  public async submitOrder(params: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price?: number;
    orderType: 'MARKET' | 'LIMIT';
  }): Promise<ServerOrderSubmittedResponse> {
    if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
      throw new Error('Cannot submit order: WebSocket not connected');
    }

    const requestId = `order-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    const message: ClientSubmitOrderMessage = {
      type: 'submit_order',
      requestId,
      timestamp: Date.now(),
      deviceId: DeviceIdManager.getInstance().getDeviceId(),
      data: {
        symbol: params.symbol,
        side: params.side,
        quantity: params.quantity,
        price: params.price,
        orderType: params.orderType
      }
    };
    
    try {
      this.webSocket.send(JSON.stringify(message));
      this.logger.debug(`Order submission request sent: ${requestId}`);
    } catch (error: any) {
      this.logger.error('Failed to send order submit message', { error: error.message });
      throw error;
    }

    return this.createResponsePromise<ServerOrderSubmittedResponse>(requestId, 'order_submitted');
  }

  // Method to cancel an order via WebSocket
  public async cancelOrder(orderId: string): Promise<ServerOrderCancelledResponse> {
    if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
      throw new Error('Cannot cancel order: WebSocket not connected');
    }

    const requestId = `cancel-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    const message: ClientCancelOrderMessage = {
      type: 'cancel_order',
      requestId,
      timestamp: Date.now(),
      deviceId: DeviceIdManager.getInstance().getDeviceId(),
      data: {
        orderId
      }
    };

    try {
      this.webSocket.send(JSON.stringify(message));
      this.logger.debug(`Order cancellation request sent: ${requestId}`);
    } catch (error: any) {
      this.logger.error('Failed to send order cancel message', { error: error.message });
      throw error;
    }

    return this.createResponsePromise<ServerOrderCancelledResponse>(requestId, 'order_cancelled');
  }

  /**
   * Requests session information from the server.
   */
  public async requestSessionInfo(): Promise<ServerSessionInfoResponse> {
    if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
      throw new Error('Cannot request session info: WebSocket not connected');
    }

    const requestId = `session-info-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    const deviceId = DeviceIdManager.getInstance().getDeviceId();

    this.logger.warn('Sending session info request', {
      requestId,
      deviceId,
      tokenExists: !!this.tokenManager.getTokens(),
      tokenExpiration: this.tokenManager.getTokens()?.expiresAt,
      currentTime: Date.now()
    });
    
    const message: ClientSessionInfoRequest = {
      type: 'request_session_info',
      requestId,
      timestamp: Date.now(),
      deviceId: DeviceIdManager.getInstance().getDeviceId()
    };

    try {
      this.webSocket.send(JSON.stringify(message));
      this.logger.debug(`Session info request sent: ${requestId}`);
    } catch (error: any) {
      this.logger.error('Failed to send session info request message', { 
        error: error.message,
        deviceId,
        requestId
      });
      throw error;
    }

    return this.createResponsePromise<ServerSessionInfoResponse>(requestId, 'session_info');
  }

  /**
   * Stops the current session.
   */
  public async stopSession(): Promise<ServerStopSessionResponse> {
    if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
      throw new Error('Cannot stop session: WebSocket not connected');
    }

    const requestId = `stop-session-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    const message: ClientStopSessionRequest = {
      type: 'stop_session',
      requestId,
      timestamp: Date.now(),
      deviceId: DeviceIdManager.getInstance().getDeviceId()
    };

    try {
      this.webSocket.send(JSON.stringify(message));
      this.logger.debug(`Stop session request sent: ${requestId}`);
    } catch (error: any) {
      this.logger.error('Failed to send stop session message', { error: error.message });
      throw error;
    }

    return this.createResponsePromise<ServerStopSessionResponse>(requestId, 'session_stopped');
  }

  /**
   * Starts the simulator.
   */
  public async startSimulator(): Promise<ServerSimulatorStartedResponse> {
    if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
      throw new Error('Cannot start simulator: WebSocket not connected');
    }

    const requestId = `start-simulator-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    const message: ClientStartSimulatorMessage = {
      type: 'start_simulator',
      requestId,
      timestamp: Date.now(),
      deviceId: DeviceIdManager.getInstance().getDeviceId()
    };

    try {
      this.webSocket.send(JSON.stringify(message));
      this.logger.debug(`Start simulator request sent: ${requestId}`);
    } catch (error: any) {
      this.logger.error('Failed to send start simulator message', { error: error.message });
      throw error;
    }

    return this.createResponsePromise<ServerSimulatorStartedResponse>(requestId, 'simulator_started');
  }

  /**
   * Stops the simulator.
   */
  public async stopSimulator(): Promise<ServerSimulatorStoppedResponse> {
    if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
      throw new Error('Cannot stop simulator: WebSocket not connected');
    }

    const requestId = `stop-simulator-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    const message: ClientStopSimulatorMessage = {
      type: 'stop_simulator',
      requestId,
      timestamp: Date.now(),
      deviceId: DeviceIdManager.getInstance().getDeviceId()
    };

    try {
      this.webSocket.send(JSON.stringify(message));
      this.logger.debug(`Stop simulator request sent: ${requestId}`);
    } catch (error: any) {
      this.logger.error('Failed to send stop simulator message', { error: error.message });
      throw error;
    }

    return this.createResponsePromise<ServerSimulatorStoppedResponse>(requestId, 'simulator_stopped');
  }

  /**
   * Helper method to create a promise for WebSocket responses.
   */
  private createResponsePromise<T extends { requestId: string }>(requestId: string, eventType: keyof WebSocketEvents): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      this.logger.warn(`Creating response promise for ${String(eventType)}`, { 
        requestId, 
        pendingResponsesCount: this.pendingResponses.size 
      });

      const subscription = this.once(eventType, (result: any) => {
        this.logger.warn(`Received response for ${String(eventType)}`, {
          receivedRequestId: result.requestId,
          expectedRequestId: requestId
        });
  
        if (result.requestId === requestId) {
          resolve(result as T);
        } else {
          reject(new Error(`Mismatched requestId for ${String(eventType)}`));
        }
      });
      
      const timeoutId = window.setTimeout(() => {
        subscription.unsubscribe();
        const timeoutError = new Error(`${String(eventType)} request timed out`);
        this.logger.error(`Response promise timed out`, { 
          requestId, 
          eventType: String(eventType) 
        });
        reject(timeoutError);
      }, this.responseTimeoutMs);

      this.pendingResponses.set(requestId, {
        resolve,
        reject,
        timeoutId,
        requestId,
        requestTime: Date.now()
      });
    });
  }

  public sendMessage(type: string, payload?: any): void {
    if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
        this.logger.error(`Failed to send message type ${type}: WebSocket not connected.`);
        return;
    }
    try {
      const message = JSON.stringify({ type, payload });
      this.logger.debug(`Sending message type ${type}`);
      this.webSocket.send(message);
    } catch (error: any) {
      this.logger.error(`Error sending message type ${type}`, { error: error.message });
    }
  }

  public dispose(): void {
    if (this.isDisposed) return;
    this.logger.warn('Disposing WebSocketManager...');
    this.disconnect('manager_disposed');
    this.removeAllListeners();
    this.subscriptions.unsubscribe();
    this.connectionStatus$.complete();
    this.logger.info('WebSocketManager disposed.');
  }

  [Symbol.dispose](): void {
    this.dispose();
  }
}