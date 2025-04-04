import { EventEmitter } from '../../utils/event-emitter';
import { HeartbeatManagerDependencies } from './types';
import { DeviceIdManager } from '../../utils/device-id-manager';

export class HeartbeatManager {
  private ws: WebSocket;
  private eventEmitter: EventEmitter;
  private interval: number;
  private timeout: number;
  private heartbeatTimer: number | null = null;
  private heartbeatTimeoutTimer: number | null = null; // Added for timeout tracking
  private lastHeartbeatResponseTime: number = 0; // Track response time

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
    this.stop(); // Ensure any existing timers are cleared
    this.lastHeartbeatResponseTime = Date.now(); // Initialize response time
    this.heartbeatTimer = window.setInterval(() => {
      this.sendHeartbeat();
    }, this.interval);
    // Optionally send an initial heartbeat immediately
    // this.sendHeartbeat();
  }

  private sendHeartbeat(): void {
    if (this.ws.readyState === WebSocket.OPEN) {
      const now = Date.now();
      // Check if timeout has occurred since last successful response
      if (now - this.lastHeartbeatResponseTime > this.interval + this.timeout) {
          console.warn(`Heartbeat timeout: No response received within ${this.interval + this.timeout}ms`);
          this.eventEmitter.emit('heartbeat_timeout');
          // Consider triggering disconnect or recovery mechanism here
          // this.stop(); // Stop sending further heartbeats after timeout
          return; // Don't send a new heartbeat if timed out
      }

      const heartbeatMessage = {
        type: 'heartbeat',
        timestamp: now,
        // Use the centralized DeviceIdManager
        deviceId: DeviceIdManager.getDeviceId()
      };

      this.ws.send(JSON.stringify(heartbeatMessage));

      // Clear previous timeout timer if exists
      if (this.heartbeatTimeoutTimer !== null) {
         clearTimeout(this.heartbeatTimeoutTimer);
      }

      // Set a timer to check for response timeout specifically for *this* heartbeat
      this.heartbeatTimeoutTimer = window.setTimeout(() => {
         // This check might be redundant if the interval check above is sufficient
         // Or it can provide a more immediate timeout detection after sending
         console.warn(`Heartbeat timeout: No response for heartbeat sent at ${now}`);
         this.eventEmitter.emit('heartbeat_timeout');
         // Maybe trigger recovery here as well
      }, this.timeout);

    } else {
      console.warn('Cannot send heartbeat, WebSocket is not open.');
      // Stop trying if WS is closed
      this.stop();
    }
  }

  // Method to be called when a heartbeat *response* is received
  public handleHeartbeatResponse(): void {
    this.lastHeartbeatResponseTime = Date.now();
    // Clear the specific timeout timer for the last sent heartbeat
    if (this.heartbeatTimeoutTimer !== null) {
        clearTimeout(this.heartbeatTimeoutTimer);
        this.heartbeatTimeoutTimer = null;
    }
  }

  public stop(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
     if (this.heartbeatTimeoutTimer !== null) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }
}