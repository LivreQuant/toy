// src/services/connection/heartbeat.ts
import { getLogger } from '../../boot/logging';

import { ConnectionStatus } from '../../state/connection-state';

import { SocketClient } from './socket-client';

import { DeviceIdManager } from '../auth/device-id-manager';

import { Disposable } from '../../utils/disposable';
import { EventEmitter } from '../../utils/events';

export interface HeartbeatOptions {
  interval: number;
  timeout: number;
}


export class Heartbeat implements Disposable {
  private logger = getLogger('Heartbeat');
  private client: SocketClient;
  private options: Required<HeartbeatOptions>;
  private heartbeatIntervalId: number | null = null;
  private heartbeatTimeoutId: number | null = null;
  private isStarted: boolean = false; // This is private
  private isDisposed: boolean = false;
  private lastHeartbeatTimestamp: number = 0;
  private events = new EventEmitter<{
      timeout: void;
      response: { latency: number; deviceIdValid: boolean; simulatorStatus: string };
  }>();

  // Add a public getter method to access isStarted
  public isActive(): boolean {
      return this.isStarted && !this.isDisposed;
  }

  constructor(client: SocketClient, options?: Partial<HeartbeatOptions>) {
      this.client = client;
      
      const defaultOptions: Required<HeartbeatOptions> = {
          interval: 15000, // 15 seconds
          timeout: 5000    // 5 seconds
      };
      
      this.options = { ...defaultOptions, ...(options || {}) };
      this.logger.info('Heartbeat initialized', { options: this.options });
      
      // Setup listeners
      this.client.on('message', (message) => {
          if (message.type === 'heartbeat_ack') {
              this.handleHeartbeatResponse(message);
          }
      });
      
      // Do NOT start heartbeat automatically in constructor
  }

  public start(): void {
      if (this.isStarted || this.isDisposed) {
          this.logger.debug('Heartbeat start ignored: Already started or disposed');
          return;
      }
      
      this.logger.info('Starting heartbeats...');
      this.isStarted = true;
      
      // Log explicit start with high visibility
      this.logger.info('Heartbeat explicitly started - sending first heartbeat');
      
      // Send immediate heartbeat
      this.sendHeartbeat();
      
      // Schedule next heartbeat
      this.scheduleNextHeartbeat();
  }

  public stop(): void {
      if (!this.isStarted || this.isDisposed) {
          this.logger.debug('Heartbeat stop ignored: Not running or disposed');
          return;
      }
      
      this.logger.info('Stopping heartbeats...');
      this.isStarted = false;
      this.clearHeartbeatInterval();
      this.clearHeartbeatTimeout();
  }

  public on<T extends keyof typeof this.events.events>(
    event: T,
    callback: (data: typeof this.events.events[T]) => void
  ): { unsubscribe: () => void } {
    return this.events.on(event, callback);
  }

  private scheduleNextHeartbeat(): void {
    this.clearHeartbeatInterval();
    this.heartbeatIntervalId = window.setInterval(() => {
      this.sendHeartbeat();
    }, this.options.interval);
  }

  private sendHeartbeat(): void {
    if (!this.isStarted || this.isDisposed) return;
    
    if (this.client.getCurrentStatus() !== ConnectionStatus.CONNECTED) {
      this.logger.debug('Skipping heartbeat: WebSocket not connected');
      return;
    }
    
    this.logger.debug('Sending heartbeat');
    
    const heartbeatMsg = {
      type: 'heartbeat',
      timestamp: Date.now(),
      deviceId: DeviceIdManager.getInstance().getDeviceId()
    };
    
    try {
      this.client.send(heartbeatMsg);
      
      // Set timeout for heartbeat acknowledgment
      this.clearHeartbeatTimeout();
      this.heartbeatTimeoutId = window.setTimeout(() => {
        this.handleHeartbeatTimeout();
      }, this.options.timeout);
      
    } catch (error: any) {
      this.logger.error('Failed to send heartbeat', {
        error: error instanceof Error ? error.message : String(error)
      });
    }
  }

  private handleHeartbeatResponse(message: any): void {
    this.lastHeartbeatTimestamp = Date.now();
    
    this.logger.debug('Heartbeat Response Analysis', {
      deviceIdValid: message.deviceIdValid,
      simulatorStatus: message.simulatorStatus,
      clientTimestamp: message.clientTimestamp,
      serverTimestamp: Date.now(),
      latency: message.clientTimestamp ? (Date.now() - message.clientTimestamp) : -1
    });
    
    // Clear timeout
    this.clearHeartbeatTimeout();
    
    const latency = message.clientTimestamp ? (Date.now() - message.clientTimestamp) : -1;
    
    // Emit event
    this.events.emit('response', {
      latency,
      deviceIdValid: message.deviceIdValid,
      simulatorStatus: message.simulatorStatus
    });
  }

  private handleHeartbeatTimeout(): void {
    this.logger.error('Heartbeat timeout detected');
    this.events.emit('timeout', undefined);
  }

  private clearHeartbeatInterval(): void {
    if (this.heartbeatIntervalId !== null) {
      window.clearInterval(this.heartbeatIntervalId);
      this.heartbeatIntervalId = null;
    }
  }

  private clearHeartbeatTimeout(): void {
    if (this.heartbeatTimeoutId !== null) {
      window.clearTimeout(this.heartbeatTimeoutId);
      this.heartbeatTimeoutId = null;
    }
  }

  public dispose(): void {
    if (this.isDisposed) return;
    this.isDisposed = true;
    this.stop();
    this.events.clear();
    this.logger.info('Heartbeat disposed');
  }

  [Symbol.dispose](): void {
    this.dispose();
  }
}