import { config } from '../../config';
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { ConnectionStrategyDependencies, WebSocketOptions } from './types';

export class ConnectionStrategy {
  private tokenManager: TokenManager;
  private eventEmitter: EventEmitter;
  private options: WebSocketOptions;
  private ws: WebSocket | null = null;

  constructor({ 
    tokenManager, 
    eventEmitter, 
    options = {} 
  }: ConnectionStrategyDependencies) {
    this.tokenManager = tokenManager;
    this.eventEmitter = eventEmitter;
    this.options = {
      heartbeatInterval: 15000,
      heartbeatTimeout: 5000,
      reconnectMaxAttempts: 5,
      ...options
    };
  }

  public async connect(): Promise<WebSocket> {
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      throw new Error('No authentication token available');
    }

    const deviceId = this.generateDeviceId();
    const params = new URLSearchParams({
      token,
      deviceId,
      userAgent: navigator.userAgent
    });

    const wsUrl = `${config.wsBaseUrl}?${params.toString()}`;
    this.ws = new WebSocket(wsUrl);

    return new Promise((resolve, reject) => {
      if (!this.ws) {
        reject(new Error('Failed to create WebSocket'));
        return;
      }

      this.ws.onopen = () => {
        this.eventEmitter.emit('connected');
        resolve(this.ws!);
      };

      this.ws.onclose = (event) => {
        this.eventEmitter.emit('disconnected', {
          code: event.code,
          reason: event.reason
        });
        reject(new Error(`WebSocket closed: ${event.reason}`));
      };

      this.ws.onerror = (error) => {
        this.eventEmitter.emit('error', error);
        reject(error);
      };
    });
  }

  public disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnected');
      this.ws = null;
    }
  }

  public getWebSocket(): WebSocket | null {
    return this.ws;
  }

  private generateDeviceId(): string {
    const storageKey = 'trading_device_id';
    let deviceId = localStorage.getItem(storageKey);
    
    if (!deviceId) {
      deviceId = `device_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      localStorage.setItem(storageKey, deviceId);
    }
    
    return deviceId;
  }
}