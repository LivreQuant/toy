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
import { getLogger } from '../../boot/logging';
import {
  WebSocketMessage,
  ServerHeartbeatMessage, // Use specific type
  isServerHeartbeatMessage, // Use specific type guard
  isExchangeDataMessage,
  isOrderUpdateMessage,
  isResponseMessage,
  ResponseMessage, // Import ResponseMessage type
  SessionInvalidatedMessage,
  PortfolioDataMessage,
  RiskDataMessage,
  isPortfolioDataMessage, // Import missing type guards if needed
  isRiskDataMessage,
  isSessionInvalidatedMessage,
  isSessionReadyResponseMessage
} from './message-types';
import {
  appState,
  ConnectionStatus,
  ConnectionQuality // FIX: Import ConnectionQuality
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
  requestTime: number; // Store when request was sent for timeout measurement
}


export class WebSocketManager extends TypedEventEmitter<WebSocketEvents> implements Disposable {
  private logger = getLogger('WebSocketManager');
  private tokenManager: TokenManager;
  private webSocket: WebSocket | null = null;
  private heartbeatManager: HeartbeatManager | null = null;
  private isDisposed: boolean = false;
  // FIX: Use PendingResponse type
  private pendingResponses: Map<string, PendingResponse> = new Map();
  private options: Required<WebSocketOptions>;
  private connectionStatus$ = new BehaviorSubject<ConnectionStatus>(ConnectionStatus.DISCONNECTED);
  private readonly responseTimeoutMs = 15000; // Example: 15 second timeout for responses

  constructor(
    tokenManager: TokenManager,
    options: WebSocketOptions = {}
  ) {
    super('WebSocketManagerEvents');
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
            if (ws === this.webSocket) {
               this.handleConnectionOpen();
               resolve(true);
            } else { this.logger.warn("onopen event for outdated WebSocket."); }
            cleanup();
        };
        const closeHandler = (event: CloseEvent) => {
             this.logger.warn(`WebSocket onclose event. Code: ${event.code}`);
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
        // FIX: Ensure 'this' context is correct for handleMessage
        ws.addEventListener('message', this.handleMessage);
      });

    } catch (error: any) {
      this.logger.error('Error initiating WebSocket connection', { error: error.message });
      this.updateStateOnError(error instanceof Error ? error.message : String(error));
      AppErrorHandler.handleConnectionError(error, ErrorSeverity.HIGH, 'WebSocketConnectInitiation');
      return false;
    }
  }

   // FIX: Add public disconnect method
   public disconnect(reason: string = 'manual'): void {
      this.logger.warn(`Disconnect requested. Reason: ${reason}`);
      if (this.webSocket) {
         // Simulate a clean close event if called manually
         const event = new CloseEvent('close', {
            code: 1000, // Normal closure
            reason: reason,
            wasClean: true
         });
         this.handleConnectionClose(event); // Trigger cleanup and state update
      } else {
         this.logger.info('Disconnect called but no active WebSocket connection.');
         // Ensure state is disconnected if somehow it wasn't already
         if (this.connectionStatus$.getValue() !== ConnectionStatus.DISCONNECTED) {
             this.updateStateOnError(`Disconnected: ${reason}`);
         }
      }
   }

  private handleMessage = (event: MessageEvent): void => {
    if (this.isDisposed || event.currentTarget !== this.webSocket) return;

    try {
      const message = JSON.parse(event.data) as WebSocketMessage;
      this.logger.debug(`Received WebSocket message type: ${message.type}`, { requestId: message.requestId });

      this.emit('message', message);

      // FIX: Use specific type guard
      if (isServerHeartbeatMessage(message)) {
        this.handleHeartbeatMessage(message);
      // FIX: Check for ResponseMessage and call handler
      } else if (isResponseMessage(message)) {
        this.handleResponseMessage(message); // Call implemented handler
      } else if (isExchangeDataMessage(message)) {
        this.emit('exchange_data', message.data.symbols);
      // FIX: Use imported type guards if needed
      } else if (isPortfolioDataMessage(message)) {
          this.emit('portfolio_data', message.data);
      } else if (isRiskDataMessage(message)) {
           this.emit('risk_data', message.data);
      } else if (isOrderUpdateMessage(message)) {
        this.emit('order_update', message.data);
      // FIX: Use imported type guards if needed
      } else if (isSessionInvalidatedMessage(message)) {
          this.emit('session_invalidated', { reason: message.reason || 'Unknown reason' });
      } else if (isSessionReadyResponseMessage(message)) {
           this.emit('session_ready_response', message);
      } else {
           this.logger.warn(`Unhandled WebSocket message type: ${message.type}`);
      }

    } catch (error: any) {
      this.logger.error('Error processing WebSocket message', { error: error.message, data: event.data?.substring(0, 200) });
      this.emit('message_error', { error: error, rawData: event.data });
    }
  };


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
          // FIX: Cast 'this' if TS still complains after TypedEventEmitter logger fix (unlikely needed now)
          eventEmitter: this, // as TypedEventEmitter<any>,
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
      this.heartbeatManager.dispose(); // Use dispose if available, otherwise stop
      this.heartbeatManager = null;
    }

    const errorReason = event.reason || `Connection closed (Code: ${event.code}, Clean: ${event.wasClean})`;
    appState.updateConnectionState({
        webSocketStatus: ConnectionStatus.DISCONNECTED,
        lastConnectionError: errorReason,
        // FIX: Import and use ConnectionQuality
        quality: ConnectionQuality.UNKNOWN,
        heartbeatLatency: null,
    });
    this.connectionStatus$.next(ConnectionStatus.DISCONNECTED);

    this.cleanupWebSocket();
    // FIX: Use implemented clearPendingResponses
    this.clearPendingResponses(`connection_closed_${event.code}`);
  }

  private handleConnectionError(event: Event): void {
    if (this.isDisposed) return;
    this.logger.error('WebSocket connection error event occurred.', { event });
    appState.updateConnectionState({
        // Don't change status here, let onclose handle it
        lastConnectionError: 'WebSocket error occurred'
     });
    AppErrorHandler.handleConnectionError('WebSocket connection error', ErrorSeverity.MEDIUM, 'WebSocketManagerErrorEvent');
  }

   private updateStateOnError(errorMessage: string): void {
       appState.updateConnectionState({
           webSocketStatus: ConnectionStatus.DISCONNECTED,
           lastConnectionError: errorMessage,
           // FIX: Import and use ConnectionQuality
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
           this.heartbeatManager.dispose(); // Use dispose if available
           this.heartbeatManager = null;
       }
   }

  // FIX: Implement handleResponseMessage
  private handleResponseMessage(message: ResponseMessage): void {
      const { requestId, success, data, error } = message;
      const pending = this.pendingResponses.get(requestId);

      if (pending) {
          clearTimeout(pending.timeoutId); // Clear the timeout
          this.pendingResponses.delete(requestId); // Remove from map

          const duration = Date.now() - pending.requestTime;
          this.logger.debug(`Received response for request ${requestId} in ${duration}ms. Success: ${success}`);

          if (success) {
              pending.resolve(data); // Resolve the promise with data
          } else {
              const errorMessage = error?.message || 'Request failed with no error message';
              this.logger.error(`Request ${requestId} failed`, { error });
              // Reject the promise with an error object
              const errorObj = new Error(errorMessage);
              // Attach details if needed
              (errorObj as any).code = error?.code;
              pending.reject(errorObj);
          }
      } else {
          this.logger.warn(`Received response for unknown or timed-out request ID: ${requestId}`);
      }
  }

  // FIX: Implement clearPendingResponses
  private clearPendingResponses(reason: string): void {
      if (this.pendingResponses.size === 0) return;

      this.logger.warn(`Clearing ${this.pendingResponses.size} pending request(s) due to: ${reason}`);
      this.pendingResponses.forEach((pending, requestId) => {
          clearTimeout(pending.timeoutId);
          pending.reject(new Error(`Request cancelled: ${reason}`));
      });
      this.pendingResponses.clear();
  }


  // FIX: Use correct type ServerHeartbeatMessage and complete last line
  private handleHeartbeatMessage(message: ServerHeartbeatMessage): void {
    if (this.isDisposed) return;
    this.heartbeatManager?.handleHeartbeatResponse();

    const now = Date.now();
    const latency = message.timestamp ? (now - message.timestamp) : -1;

     this.emit('heartbeat', {
       timestamp: message.timestamp || now, // Use now if server didn't send timestamp
       latency: latency >= 0 ? latency : -1,
       simulatorStatus: message.simulatorStatus,
       deviceId: message.deviceId // FIX: Complete property access
     });

     // Update AppState directly with quality based on latency
      const quality = appState.calculateConnectionQuality(latency);
      appState.updateConnectionState({
         lastHeartbeatTime: now,
         heartbeatLatency: latency >= 0 ? latency : null,
         quality: quality,
         ...(message.simulatorStatus && { simulatorStatus: message.simulatorStatus })
      });
  } // FIX: Add closing brace for the method

  // --- Sending Messages & Handling Responses ---

  // Example: Send a message expecting a response
  public async sendRequest<T>(
        type: string,
        payload: any,
        timeout: number = this.responseTimeoutMs
    ): Promise<T> {
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

   // Example: Send a message without expecting a response
   public sendMessage(type: string, payload?: any): void {
      if (!this.webSocket || this.webSocket.readyState !== WebSocket.OPEN) {
          this.logger.error(`Failed to send message type ${type}: WebSocket not connected.`);
          // Optionally throw an error or handle silently
          // throw new Error("WebSocket not connected");
          return;
      }
      try {
         const message = JSON.stringify({ type, payload });
         this.logger.debug(`Sending message type ${type}`);
         this.webSocket.send(message);
      } catch (error: any) {
         this.logger.error(`Error sending message type ${type}`, { error: error.message });
         // Handle serialization errors etc.
      }
   }


  // --- Disposable Implementation ---
  public dispose(): void {
    if (this.isDisposed) return;
    this.logger.warn('Disposing WebSocketManager...');
    this.isDisposed = true;
    this.disconnect('manager_disposed'); // Trigger cleanup via disconnect
    this.removeAllListeners(); // Clean up TypedEventEmitter listeners
    this.subscriptions.unsubscribe(); // Clean up internal RxJS subscriptions
    this.connectionStatus$.complete(); // Complete the subject
    this.logger.info('WebSocketManager disposed.');
  }

  [Symbol.dispose](): void {
    this.dispose();
  }
} // FIX: Add closing brace for the class