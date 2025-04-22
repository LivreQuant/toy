// src/services/websocket/socket-client.ts
import { BehaviorSubject, Observable } from 'rxjs';
import { TokenManager } from '../auth/token-manager';
import { DeviceIdManager } from '../auth/device-id-manager';
import { getLogger } from '../../boot/logging';
import { ConnectionStatus } from '../../state/connection-state';
import { config } from '../../config';
import { Disposable } from '../../utils/disposable';
import { WebSocketMessage } from '../websocket/message-types';
import { EventEmitter } from '../../utils/events';

export interface SocketClientOptions {
  autoReconnect?: boolean;
  connectTimeout?: number;
}

export class SocketClient implements Disposable {
  private socket: WebSocket | null = null;
  private tokenManager: TokenManager;
  private status$ = new BehaviorSubject<ConnectionStatus>(ConnectionStatus.DISCONNECTED);
  private logger = getLogger('SocketClient');
  private events = new EventEmitter<{
    message: WebSocketMessage;
    error: Error;
    open: void;
    close: { code: number; reason: string; wasClean: boolean };
  }>();

  private options: Required<SocketClientOptions> = {
    autoReconnect: false,
    connectTimeout: 10000
  };

  constructor(tokenManager: TokenManager, options?: Partial<SocketClientOptions>) {
    this.tokenManager = tokenManager;
    if (options) {
      this.options = { ...this.options, ...options };
    }
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
  public async connect(): Promise<boolean> {
    if (this.socket) {
      this.logger.warn('Connect called with existing socket, cleaning up previous instance');
      this.cleanup();
    }

    if (!this.tokenManager.isAuthenticated()) {
      this.logger.error('Cannot connect: Not authenticated');
      this.status$.next(ConnectionStatus.DISCONNECTED);
      return false;
    }

    const currentStatus = this.status$.getValue();
    if (currentStatus === ConnectionStatus.CONNECTING || currentStatus === ConnectionStatus.CONNECTED) {
      this.logger.warn(`Connect call ignored: WebSocket status is already ${currentStatus}`);
      return currentStatus === ConnectionStatus.CONNECTED;
    }

    try {
      this.logger.info('Initiating WebSocket connection...');
      this.status$.next(ConnectionStatus.CONNECTING);

      const token = await this.tokenManager.getAccessToken();
      if (!token) {
        throw new Error('Failed to get authentication token for WebSocket');
      }

      const deviceId = DeviceIdManager.getInstance().getDeviceId();
      const params = new URLSearchParams({ token, deviceId });
      const wsUrl = `${config.wsBaseUrl}?${params.toString()}`;

      this.socket = new WebSocket(wsUrl);
      
      return new Promise<boolean>((resolve) => {
        const timeoutId = setTimeout(() => {
          this.logger.error('WebSocket connection attempt timed out');
          if (this.status$.getValue() === ConnectionStatus.CONNECTING) {
            this.cleanup();
            this.status$.next(ConnectionStatus.DISCONNECTED);
            resolve(false);
          }
        }, this.options.connectTimeout);

        this.socket!.addEventListener('open', () => {
          clearTimeout(timeoutId);
          this.logger.info('WebSocket connection established');
          this.status$.next(ConnectionStatus.CONNECTED);
          this.events.emit('open', undefined);
          resolve(true);
        });

        this.socket!.addEventListener('error', (event) => {
          this.logger.error('WebSocket connection error', { event });
          this.events.emit('error', new Error('WebSocket connection error'));
          // Keep the CONNECTING status - error doesn't mean disconnected
          // The close event will follow if connection truly failed
        });

        this.socket!.addEventListener('close', (event) => {
          clearTimeout(timeoutId);
          this.handleClose(event);
          if (this.status$.getValue() === ConnectionStatus.CONNECTING) {
            resolve(false);
          }
        });

        this.socket!.addEventListener('message', this.handleMessage);
      });
    } catch (error: any) {
      this.logger.error('Error initiating WebSocket connection', {
        error: error instanceof Error ? error.message : String(error)
      });
      this.status$.next(ConnectionStatus.DISCONNECTED);
      return false;
    }
  }

  // Disconnect from the WebSocket server
  public disconnect(reason: string = 'manual'): void {
    this.logger.info(`Disconnecting WebSocket. Reason: ${reason}`);
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
      this.logger.error('Cannot send message: WebSocket not connected');
      return false;
    }

    try {
      this.socket.send(typeof data === 'string' ? data : JSON.stringify(data));
      return true;
    } catch (error: any) {
      this.logger.error('Error sending WebSocket message', {
        error: error instanceof Error ? error.message : String(error)
      });
      return false;
    }
  }

  // Listen for events
  public on<T extends keyof typeof this.events.events>(
    event: T,
    callback: (data: typeof this.events.events[T]) => void
  ): { unsubscribe: () => void } {
    return this.events.on(event, callback);
  }

  // Handle incoming messages
  private handleMessage = (event: MessageEvent): void => {
    try {
      const message = JSON.parse(event.data) as WebSocketMessage;
      this.events.emit('message', message);
    } catch (error: any) {
      this.logger.error('Error parsing WebSocket message', {
        error: error instanceof Error ? error.message : String(error),
        data: typeof event.data === 'string' ? event.data.substring(0, 100) : 'non-string data'
      });
      this.events.emit('error', error instanceof Error ? error : new Error(String(error)));
    }
  };

  // Handle connection close
  private handleClose = (event: CloseEvent): void => {
    this.logger.info(`WebSocket connection closed. Code: ${event.code}, Reason: ${event.reason}, Clean: ${event.wasClean}`);
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
          this.logger.warn('Error closing WebSocket during cleanup');
        }
      }
      
      this.socket = null;
    }
  }

  // Implement Disposable interface
  public dispose(): void {
    this.disconnect('disposed');
    this.events.clear();
    this.status$.complete();
  }

  [Symbol.dispose](): void {
    this.dispose();
  }
}