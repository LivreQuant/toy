import { EventEmitter } from '../../utils/event-emitter';
import { HeartbeatManagerDependencies } from './types';
import { DeviceIdManager } from '../../utils/device-id-manager';

export class HeartbeatManager {
  private ws: WebSocket;
  private eventEmitter: EventEmitter;
  private interval: number;
  private timeout: number;
  private heartbeatTimer: number | null = null;
  private lastHeartbeatTime: number = 0;

  constructor({ 
    ws, 
    eventEmitter, 
    options = {} 
  }: HeartbeatManagerDependencies) {
    this.ws = ws;
    this.eventEmitter = eventEmitter;
    this.interval = options.interval || 15000;
    this.timeout = options.timeout || 5000;
  }

  public start(): void {
    this.stop();
    this.heartbeatTimer = window.setInterval(() => {
      this.sendHeartbeat();
    }, this.interval);
  }

  private sendHeartbeat(): void {
    if (this.ws.readyState === WebSocket.OPEN) {
      const now = Date.now();
      const heartbeatMessage = {
        type: 'heartbeat',
        timestamp: now,
        deviceId: DeviceIdManager.getDeviceId()
      };

      this.lastHeartbeatTime = now;
      this.ws.send(JSON.stringify(heartbeatMessage));

      setTimeout(() => {
        if (now === this.lastHeartbeatTime) {
          this.eventEmitter.emit('heartbeat_timeout');
        }
      }, this.timeout);
    }
  }

  public stop(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private getDeviceId(): string {
    const storageKey = 'trading_device_id';
    let deviceId = localStorage.getItem(storageKey);
    
    if (!deviceId) {
      deviceId = `device_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      localStorage.setItem(storageKey, deviceId);
    }
    
    return deviceId;
  }
}