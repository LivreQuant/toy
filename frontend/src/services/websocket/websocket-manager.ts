// src/services/websocket/websocket-manager.ts
import { BehaviorSubject, Observable, Subscription } from 'rxjs';
import { filter, map } from 'rxjs/operators';
import { TokenManager } from '../auth/token-manager';
import { WebSocketOptions } from './types';
import { DeviceIdManager } from '../../utils/device-id-manager';
import { Disposable } from '../../utils/disposable';
import { config } from '../../config';
import { AppErrorHandler } from '../../utils/app-error-handler';
import { ErrorSeverity } from '../../utils/error-handler';
import { TypedEventEmitter } from '../../utils/typed-event-emitter';
import { EnhancedLogger } from '../../utils/enhanced-logger'; // Import if needed by constructor injection
import { getLogger } from '../../boot/logging';
import {
  WebSocketMessage,
  ServerHeartbeatMessage,
  isServerHeartbeatMessage,
  isExchangeDataMessage,
  isOrderUpdateMessage,
  isResponseMessage,
  ResponseMessage,
  SessionInvalidatedMessage,
  PortfolioDataMessage,
  RiskDataMessage,
  isPortfolioDataMessage,
  isRiskDataMessage,
  isSessionInvalidatedMessage,
  isSessionReadyResponseMessage
} from './message-types';
import {
  appState,
  ConnectionStatus,
  ConnectionQuality
} from '../state/app-state.service';
import { HeartbeatManager } from './heartbeat-manager';

// Define all WebSocket specific event types
export interface WebSocketEvents {
  message: WebSocketMessage;
  heartbeat: {
    timestamp: number;
    latency: number;
    simulatorStatus?: string;
    deviceId?: string;
  };
  message_error: { error: Error; rawData: any };
  exchange_data: Record<string, any>;
  portfolio_data: PortfolioDataMessage['data'];
  risk_data: RiskDataMessage['data'];
  order_update: any;
  session_ready_response: any;
  session_invalidated: { reason: string };
}

// Structure for pending request promises
interface PendingResponse {
  resolve: (value: any) => void;
  reject: (reason?: any) => void;
  timeoutId: number;
  requestTime: number;
}


export class WebSocketManager extends TypedEventEmitter<WebSocketEvents> implements Disposable {
  // Note: Inherits 'protected logger: EnhancedLogger' from base class
  private tokenManager: TokenManager;
  private webSocket: WebSocket | null = null;
  private heartbeatManager: HeartbeatManager | null = null;
  // FIX: Remove duplicate private declaration of isDisposed
  // private isDisposed: boolean = false;
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
        heartbeatInterval: 15000,
        heartbeatTimeout: 5000,
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
      if (!token) throw new Error('Failed to get authentication token for WebSocket');

      const deviceId = DeviceIdManager.getInstance().getDeviceId();
      const params = new URLSearchParams({ token, deviceId });
      const wsUrl = `${config.wsBaseUrl}?${params.toString()}`;
      this.logger.debug(`Connecting to WebSocket URL: ${config.wsBaseUrl}`);

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
      // Attempt parsing first
      const message = JSON.parse(event.data);
      // Log basic info if parse succeeds
      this.logger.debug(`Received WebSocket message type: ${message?.type}`, { requestId: message?.requestId });

      // Emit generic message event
      this.emit('message', message as WebSocketMessage); // Cast needed here after initial parse

      // --- Handle specific message types ---
      // Type guards expect the correctly typed WebSocketMessage union
      if (isServerHeartbeatMessage(message)) {
        this.handleHeartbeatMessage(message);
      } else if (isResponseMessage(message)) {
        this.handleResponseMessage(message);
      } else if (isExchangeDataMessage(message)) {
        this.emit('exchange_data', message.data.symbols);
      } else if (isPortfolioDataMessage(message)) {
          this.emit('portfolio_data', message.data);
      } else if (isRiskDataMessage(message)) {
           this.emit('risk_data', message.data);
      } else if (isOrderUpdateMessage(message)) {
        this.emit('order_update', message.data);
      } else if (isSessionInvalidatedMessage(message)) {
          this.emit('session_invalidated', { reason: message.reason || 'Unknown reason' });
      } else if (isSessionReadyResponseMessage(message)) {
           this.emit('session_ready_response', message);
      } else {
           // FIX: Refine check for unhandled types, cast to any for the 'in' check
           const potentialMessage = message as any; // Cast to any for the check
           if (typeof potentialMessage === 'object' && potentialMessage && 'type' in potentialMessage) {
               this.logger.warn(`Unhandled WebSocket message type: ${potentialMessage.type}`); // Use potentialMessage here
           } else {
               this.logger.error('Received unhandled WebSocket message with unknown structure', { data: message });
           }
      }

    } catch (error: any) {
      this.logger.error('Error processing WebSocket message', { error: error.message, data: event.data?.substring(0, 200) });
      this.emit('message_error', { error: error, rawData: event.data });
    }
  }; // handleMessage method ends here


  private handleConnectionOpen(): void {
    if (this.isDisposed) return;
    this.logger.info('WebSocket connection established');
    appState.updateConnectionState({
        webSocketStatus: ConnectionStatus.CONNECTED,
        lastConnectionError: null,
    });
    this.connectionStatus$.next(ConnectionStatus.CONNECTED);

    if (!this.heartbeatManager && this.webSocket) {
        this.heartbeatManager = new HeartbeatManager({
          ws: this.webSocket,
          // FIX: Type 'this' should be assignable now with protected logger
          eventEmitter: this,
          options: {
            interval: this.options.heartbeatInterval,
            timeout: this.options.heartbeatTimeout
          }
        });
        this.heartbeatManager.start();
    }
  }

  private handleConnectionClose(event: CloseEvent): void {
    if (this.isDisposed) return;
    this.logger.warn(`WebSocket connection closed. Code: ${event.code}, Reason: "${event.reason}", Clean: ${event.wasClean}`);

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
    this.logger.error('WebSocket connection error event occurred.', { event });
    appState.updateConnectionState({ lastConnectionError: 'WebSocket error occurred' });
    AppErrorHandler.handleConnectionError('WebSocket connection error', ErrorSeverity.MEDIUM, 'WebSocketManagerErrorEvent');
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

  private handleResponseMessage(message: ResponseMessage): void {
      const { requestId, success, data, error } = message;
      const pending = this.pendingResponses.get(requestId);

      if (pending) {
          clearTimeout(pending.timeoutId);
          this.pendingResponses.delete(requestId);

          const duration = Date.now() - pending.requestTime;
          this.logger.debug(`Received response for request ${requestId} in ${duration}ms. Success: ${success}`);

          if (success) {
              pending.resolve(data);
          } else {
              const errorMessage = error?.message || 'Request failed with no error message';
              this.logger.error(`Request ${requestId} failed`, { error });
              const errorObj = new Error(errorMessage);
              (errorObj as any).code = error?.code;
              pending.reject(errorObj);
          }
      } else {
          this.logger.warn(`Received response for unknown or timed-out request ID: ${requestId}`);
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


  private handleHeartbeatMessage(message: ServerHeartbeatMessage): void {
    if (this.isDisposed) return;
    this.heartbeatManager?.handleHeartbeatResponse();

    const now = Date.now();
    const latency = message.timestamp ? (now - message.timestamp) : -1;

     this.emit('heartbeat', {
       timestamp: message.timestamp || now,
       latency: latency >= 0 ? latency : -1,
       simulatorStatus: message.simulatorStatus,
       deviceId: message.deviceId
     });

      const quality = appState.calculateConnectionQuality(latency);
      appState.updateConnectionState({
         lastHeartbeatTime: now,
         heartbeatLatency: latency >= 0 ? latency : null,
         quality: quality,
         ...(message.simulatorStatus && { simulatorStatus: message.simulatorStatus })
      });
  }

  // --- Sending Messages & Handling Responses ---
  public async sendRequest<T>(type: string, payload: any, timeout: number = this.responseTimeoutMs): Promise<T> {
        if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
            throw new Error("WebSocket not connected");
        }
        const requestId = `${type}-${Date.now()}-${Math.random().toString(16).substring(2, 8)}`;
        const message = { type, payload, requestId };

        return new Promise<T>((resolve, reject) => {
            const timeoutId = window.setTimeout(() => {
                if (this.pendingResponses.has(requestId)) {
                    this.logger.error(`Request ${requestId} timed out after ${timeout}ms`);
                    this.pendingResponses.delete(requestId);
                    reject(new Error(`Request timed out after ${timeout}ms`));
                }
            }, timeout);
            this.pendingResponses.set(requestId, { resolve, reject, timeoutId, requestTime: Date.now() });
            try {
                this.logger.debug(`Sending request ${requestId} (type: ${type})`);
                this.webSocket?.send(JSON.stringify(message));
            } catch (error: any) {
                this.logger.error(`Failed to send request ${requestId}`, { error: error.message });
                clearTimeout(timeoutId);
                this.pendingResponses.delete(requestId);
                reject(error);
            }
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

  // --- Disposable Implementation ---
  public dispose(): void {
    if (this.isDisposed) return;
    this.logger.warn('Disposing WebSocketManager...');
    this.disconnect('manager_disposed');
    this.removeAllListeners();
    this.subscriptions.unsubscribe(); // Now valid
    this.connectionStatus$.complete();
    this.logger.info('WebSocketManager disposed.');
  }

  [Symbol.dispose](): void {
    this.dispose();
  }
}