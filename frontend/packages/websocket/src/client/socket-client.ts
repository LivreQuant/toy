// frontend_dist/packages/websocket/src/client/socket-client.ts
import { BehaviorSubject, Observable } from 'rxjs';
import { getLogger } from '@trading-app/logging';
import { TokenManager, DeviceIdManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { Disposable } from '@trading-app/utils';
import { EventEmitter } from '@trading-app/utils';

import { WebSocketMessage } from '../types/message-types';
import { SocketClientOptions, ConfigService } from '../types/connection-types';

// 🚨 NEW: Instance counter for debugging
let socketClientInstanceCounter = 0;

export class SocketClient implements Disposable {
  private logger = getLogger('SocketClient');

  private socket: WebSocket | null = null;
  private status$ = new BehaviorSubject<ConnectionStatus>(ConnectionStatus.DISCONNECTED);
  private events = new EventEmitter<{
    message: WebSocketMessage;
    error: Error;
    open: void;
    close: { code: number; reason: string; wasClean: boolean };
  }>();

  private options: Required<SocketClientOptions>;
  private readonly instanceId: number;

  constructor(
    private tokenManager: TokenManager,
    private configService: ConfigService,
    options?: Partial<SocketClientOptions>
  ) {
    this.options = {
      autoReconnect: false,
      connectTimeout: 10000,
      secureConnection: false,
      ...options
    };
    
    // 🚨 NEW: Track instance creation
    this.instanceId = ++socketClientInstanceCounter;
    this.logger.info(`🔌 SocketClient instance #${this.instanceId} created`);
  }

  // 🚨 NEW: Get instance ID for debugging
  public getInstanceId(): number {
    return this.instanceId;
  }

  // 🚨 NEW: Public getter for socket (for debugging)
  public getSocket(): WebSocket | null {
    return this.socket;
  }

  // 🚨 NEW: Public getter for socket state info
  public getSocketInfo(): {
    hasSocket: boolean;
    readyState?: number;
    readyStateText?: string;
    url?: string;
  } {
    return {
      hasSocket: !!this.socket,
      readyState: this.socket?.readyState,
      readyStateText: this.socket ? this.getReadyStateText(this.socket.readyState) : undefined,
      url: this.socket?.url
    };
  }

  public hasActiveSocket(): boolean {
    return !!(this.socket && this.socket.readyState === WebSocket.OPEN);
  }

  // Get the connection status observable
  public getStatus(): Observable<ConnectionStatus> {
    return this.status$.asObservable();
  }

  // Get the current connection status
  public getCurrentStatus(): ConnectionStatus {
    return this.status$.getValue();
  }

  // Connect to the WebSocket server
  public async connect(bookId: string): Promise<boolean> {
    if (this.socket) {
      this.logger.warn(`SocketClient #${this.instanceId}: Connect called with existing socket, cleaning up previous instance`);
      this.cleanup();
    }

    if (!this.tokenManager.isAuthenticated()) {
      this.logger.error(`SocketClient #${this.instanceId}: Cannot connect: Not authenticated`);
      this.status$.next(ConnectionStatus.DISCONNECTED);
      return false;
    }

    const currentStatus = this.status$.getValue();
    if (currentStatus === ConnectionStatus.CONNECTING || currentStatus === ConnectionStatus.CONNECTED) {
      this.logger.warn(`SocketClient #${this.instanceId}: Connect call ignored: WebSocket status is already ${currentStatus}`);
      return currentStatus === ConnectionStatus.CONNECTED;
    }

    try {
      this.logger.info(`🚀 SocketClient #${this.instanceId}: Initiating WebSocket connection...`);
      this.status$.next(ConnectionStatus.CONNECTING);

      const token = await this.tokenManager.getAccessToken();
      if (!token) {
        throw new Error('Failed to get authentication token for WebSocket');
      }

      const csrfToken = await this.tokenManager.getCsrfToken();
      const deviceId = DeviceIdManager.getInstance().getDeviceId();
      
      const params = new URLSearchParams({ 
        token, 
        bookId,
        deviceId,
        csrfToken
      });

      // Get the base WebSocket URL from config service
      const baseWsUrl = this.configService.getWebSocketUrl();
      
      // Log the URL construction process
      this.logger.info(`🔍 SocketClient #${this.instanceId}: Constructing connection URL`, {
        baseWsUrl,
        hasToken: !!token,
        hasBookId: !!bookId,
        hasDeviceId: !!deviceId,
        hasCsrfToken: !!csrfToken,
        paramsString: params.toString(),
        configServiceType: this.configService.constructor.name
      });

      const wsUrl = `${baseWsUrl}?${params.toString()}`;
      
      // Log the final URL (but mask sensitive tokens)
      const maskedUrl = wsUrl.replace(/token=[^&]+/, 'token=***MASKED***')
                            .replace(/csrfToken=[^&]+/, 'csrfToken=***MASKED***');
      
      this.logger.info(`🔗 SocketClient #${this.instanceId}: Final URL constructed`, {
        maskedUrl,
        urlLength: wsUrl.length,
        protocol: wsUrl.startsWith('wss:') ? 'secure' : 'insecure',
        hostname: this.extractHostname(wsUrl),
        port: this.extractPort(wsUrl)
      });

      this.socket = new WebSocket(wsUrl);
      
      return new Promise<boolean>((resolve) => {
        const timeoutId = setTimeout(() => {
          this.logger.error(`❌ SocketClient #${this.instanceId}: Connection attempt timed out`, {
            timeoutMs: this.options.connectTimeout,
            maskedUrl,
            socketReadyState: this.socket?.readyState
          });
          if (this.status$.getValue() === ConnectionStatus.CONNECTING) {
            this.cleanup();
            this.status$.next(ConnectionStatus.DISCONNECTED);
            resolve(false);
          }
        }, this.options.connectTimeout);

        this.socket!.addEventListener('open', () => {
          clearTimeout(timeoutId);
          this.logger.info(`✅ SocketClient #${this.instanceId}: Connection established successfully`, {
            maskedUrl,
            readyState: this.socket?.readyState,
            extensions: this.socket?.extensions,
            protocol: this.socket?.protocol
          });
          this.status$.next(ConnectionStatus.CONNECTED);
          this.events.emit('open', undefined);
          resolve(true);
        });

        this.socket!.addEventListener('error', (event) => {
          this.logger.error(`❌ SocketClient #${this.instanceId}: Connection error`, { 
            event,
            maskedUrl,
            readyState: this.socket?.readyState,
            errorType: event.type,
            timeStamp: event.timeStamp
          });
          this.events.emit('error', new Error(`WebSocket connection error: ${event.type}`));
        });

        this.socket!.addEventListener('close', (event) => {
          clearTimeout(timeoutId);
          this.logger.warn(`🔌 SocketClient #${this.instanceId}: Connection closed during connection attempt`, {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
            maskedUrl,
            timeStamp: event.timeStamp
          });
          this.handleClose(event);
          if (this.status$.getValue() === ConnectionStatus.CONNECTING) {
            resolve(false);
          }
        });

        this.socket!.addEventListener('message', this.handleMessage);
      });
    } catch (error: any) {
      this.logger.error(`💥 SocketClient #${this.instanceId}: Error initiating connection`, {
        error: error instanceof Error ? error.message : String(error),
        errorStack: error instanceof Error ? error.stack : undefined,
        errorName: error instanceof Error ? error.name : 'Unknown'
      });
      this.status$.next(ConnectionStatus.DISCONNECTED);
      return false;
    }
  }

  // Helper method to extract hostname from URL for logging
  private extractHostname(url: string): string {
    try {
      return new URL(url).hostname;
    } catch {
      return 'invalid-url';
    }
  }

  // Helper method to extract port from URL for logging
  private extractPort(url: string): string {
    try {
      const urlObj = new URL(url);
      return urlObj.port || (urlObj.protocol === 'wss:' ? '443' : '80');
    } catch {
      return 'unknown';
    }
  }

  // Disconnect from the WebSocket server
  public disconnect(reason: string = 'manual'): void {
    this.logger.info(`SocketClient #${this.instanceId}: Disconnecting. Reason: ${reason}`);
    if (this.socket) {
      if (this.socket.readyState === WebSocket.OPEN) {
        this.socket.close(1000, reason);
      } else {
        this.cleanup();
      }
    }
    this.status$.next(ConnectionStatus.DISCONNECTED);
  }

  // Send a message to the WebSocket server
  public send(data: any): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.logger.error(`SocketClient #${this.instanceId}: Cannot send message: WebSocket not connected`, {
        hasSocket: !!this.socket,
        readyState: this.socket?.readyState,
        readyStateText: this.socket ? this.getReadyStateText(this.socket.readyState) : 'no socket',
        instanceId: this.instanceId
      });
      return false;
    }

    try {
      const messageStr = typeof data === 'string' ? data : JSON.stringify(data);
      this.socket.send(messageStr);
      this.logger.debug(`📤 SocketClient #${this.instanceId}: Message sent`, {
        messageType: typeof data === 'object' && data.type ? data.type : 'unknown',
        messageLength: messageStr.length
      });
      return true;
    } catch (error: any) {
      this.logger.error(`SocketClient #${this.instanceId}: Error sending message`, {
        error: error instanceof Error ? error.message : String(error),
        messageType: typeof data === 'object' && data.type ? data.type : 'unknown'
      });
      return false;
    }
  }

  // Helper method to get readable ready state
  private getReadyStateText(readyState: number): string {
    switch (readyState) {
      case WebSocket.CONNECTING: return 'CONNECTING';
      case WebSocket.OPEN: return 'OPEN';
      case WebSocket.CLOSING: return 'CLOSING';
      case WebSocket.CLOSED: return 'CLOSED';
      default: return `UNKNOWN(${readyState})`;
    }
  }

  // Listen for events
  public on<T extends keyof {
    message: WebSocketMessage;
    error: Error;
    open: void;
    close: { code: number; reason: string; wasClean: boolean };
  }>(
    event: T,
    callback: (data: T extends 'message' ? WebSocketMessage : 
                   T extends 'error' ? Error : 
                   T extends 'open' ? void : 
                   { code: number; reason: string; wasClean: boolean }) => void
  ): { unsubscribe: () => void } {
    return this.events.on(event as any, callback as any);
  }

  // Handle incoming messages
  private handleMessage = (event: MessageEvent): void => {
    try {
      const message = JSON.parse(event.data) as WebSocketMessage;
      this.logger.debug(`📥 SocketClient #${this.instanceId}: Message received`, {
        messageType: message.type,
        timestamp: message.timestamp,
        hasRequestId: !!message.requestId,
        dataLength: event.data.length
      });
      this.events.emit('message', message);
    } catch (error: any) {
      this.logger.error(`SocketClient #${this.instanceId}: Error parsing message`, {
        error: error instanceof Error ? error.message : String(error),
        data: typeof event.data === 'string' ? event.data.substring(0, 100) : 'non-string data',
        dataType: typeof event.data
      });
      this.events.emit('error', error instanceof Error ? error : new Error(String(error)));
    }
  };

  // Handle connection close
  private handleClose = (event: CloseEvent): void => {
    this.logger.info(`SocketClient #${this.instanceId}: Connection closed. Code: ${event.code}, Reason: ${event.reason}, Clean: ${event.wasClean}`, {
      code: event.code,
      reason: event.reason,
      wasClean: event.wasClean,
      timeStamp: event.timeStamp
    });
    this.cleanup();
    this.status$.next(ConnectionStatus.DISCONNECTED);
    this.events.emit('close', {
      code: event.code,
      reason: event.reason,
      wasClean: event.wasClean
    });
  };

  // Clean up WebSocket resources
  private cleanup(): void {
    if (this.socket) {
      this.logger.debug(`🧹 SocketClient #${this.instanceId}: Cleaning up resources`, {
        readyState: this.getReadyStateText(this.socket.readyState)
      });
      
      this.socket.removeEventListener('message', this.handleMessage);
      this.socket.removeEventListener('close', this.handleClose);
      this.socket.onopen = null;
      this.socket.onclose = null;
      this.socket.onerror = null;

      if (this.socket.readyState === WebSocket.OPEN || 
          this.socket.readyState === WebSocket.CONNECTING) {
        try {
          this.socket.close(1000, 'Client cleanup');
        } catch (e) {
          this.logger.warn(`SocketClient #${this.instanceId}: Error closing WebSocket during cleanup`, {
            error: e instanceof Error ? e.message : String(e)
          });
        }
      }
      
      this.socket = null;
    }
  }

  // Implement Disposable interface
  public dispose(): void {
    this.logger.info(`🗑️ SocketClient #${this.instanceId}: Disposing`);
    this.disconnect('disposed');
    this.events.clear();
    this.status$.complete();
  }
}