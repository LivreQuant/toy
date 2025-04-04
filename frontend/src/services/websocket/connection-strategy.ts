import { config } from '../../config';
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { DeviceIdManager } from '../../utils/device-id-manager';
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

    // Use the centralized DeviceIdManager
    const deviceId = DeviceIdManager.getDeviceId();
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
        // Pass the actual event object or relevant details
        this.eventEmitter.emit('disconnected', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean
        });
        // Rejecting here might be unwanted if disconnects are handled elsewhere
        // Consider removing reject or making it conditional
        // reject(new Error(`WebSocket closed: ${event.reason}`));
      };

      this.ws.onerror = (event) => { // event is usually of type Event, not Error
        console.error('WebSocket error event:', event);
        this.eventEmitter.emit('error', new Error('WebSocket connection error')); // Emit a standard Error
        reject(new Error('WebSocket connection error'));
      };
    });
  }

  public disconnect(): void {
    if (this.ws) {
      // Ensure listeners are removed before closing to prevent race conditions
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onerror = null;
      this.ws.onclose = null;
      if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
         this.ws.close(1000, 'Client disconnected');
      }
      this.ws = null;
    }
  }

  public getWebSocket(): WebSocket | null {
    return this.ws;
  }
}