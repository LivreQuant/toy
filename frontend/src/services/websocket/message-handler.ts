import { EventEmitter } from '../../utils/event-emitter';
import { HeartbeatData } from './types';

export class WebSocketMessageHandler {
  private eventEmitter: EventEmitter;
  private pendingResponses: Map<string, Function> = new Map();
  private messageListeners: Map<string, Function[]> = new Map();

  constructor(eventEmitter: EventEmitter) {
    this.eventEmitter = eventEmitter;
  }

  public on(event: string, listener: Function): void {
    if (!this.messageListeners.has(event)) {
      this.messageListeners.set(event, []);
    }
    this.messageListeners.get(event)?.push(listener);
  }

  public off(event: string, listener: Function): void {
    const listeners = this.messageListeners.get(event);
    if (listeners) {
      this.messageListeners.set(event, 
        listeners.filter(l => l !== listener)
      );
    }
  }

  public handleMessage(event: MessageEvent): void {
    try {
      const message = JSON.parse(event.data);
      
      // Trigger message listeners
      const listeners = this.messageListeners.get('message') || [];
      listeners.forEach(listener => listener(message));
      
      switch(message.type) {
        case 'heartbeat':
          this.handleHeartbeat(message);
          break;
        case 'claim_master':
          this.handleClaimMaster(message);
          break;
        case 'session_invalidated':
          this.handleSessionInvalidated(message);
          break;
        case 'session_ready_response':
          this.eventEmitter.emit('message', message);
          break;
        case 'response':
          this.handleResponse(message);
          break;
        default:
          this.eventEmitter.emit('message', message);
      }
    } catch (error) {
      this.eventEmitter.emit('parse_error', { 
        error, 
        rawData: event.data 
      });
    }
  }

  private handleHeartbeat(message: HeartbeatData): void {
    this.eventEmitter.emit('heartbeat', {
      timestamp: message.timestamp,
      isMaster: message.isMaster,
      simulatorStatus: message.simulatorStatus,
      deviceId: message.deviceId
    });
  }

  private handleClaimMaster(message: { deviceId: string }): void {
    this.eventEmitter.emit('claim_master', {
      deviceId: message.deviceId
    });
  }

  private handleSessionInvalidated(message: { reason: string }): void {
    this.eventEmitter.emit('session_invalidated', {
      reason: message.reason
    });
  }

  private handleResponse(message: any): void {
    const { requestId } = message;
    if (this.pendingResponses.has(requestId)) {
      const resolver = this.pendingResponses.get(requestId);
      resolver?.(message);
      this.pendingResponses.delete(requestId);
    }
  }

  public createRequestWithResponse(message: any): Promise<any> {
    return new Promise((resolve, reject) => {
      const requestId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      
      const messageWithId = { ...message, requestId };
      
      this.pendingResponses.set(requestId, resolve);
      
      const timeoutId = setTimeout(() => {
        if (this.pendingResponses.has(requestId)) {
          this.pendingResponses.delete(requestId);
          reject(new Error(`Request timeout for ${message.type}`));
        }
      }, 5000);

      return messageWithId;
    });
  }
}