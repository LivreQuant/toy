// src/handlers/heartbeat-handler.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { EventEmitter } from '@trading-app/utils';

import { SocketClient } from '../client/socket-client';
import { ServerHeartbeatAckMessage } from '../types/message-types';
import { HeartbeatOptions, StateManager } from '../types/connection-types';

export class HeartbeatHandler {
  private logger = getLogger('HeartbeatHandler');
  private intervalId: number | null = null;
  private timeoutId: number | null = null;
  private lastTimestamp: number = 0;
  private events = new EventEmitter<{
    timeout: void;
    response: ServerHeartbeatAckMessage;
    deviceIdInvalidated: { deviceId: string; reason?: string };
  }>();

  constructor(
    private client: SocketClient,
    private stateManager: StateManager,
    private options: HeartbeatOptions
  ) {
    this.logger.info('HeartbeatHandler initialized', { options });
  }

  public start(): void {
    this.logger.info('Starting heartbeat monitoring');
    this.stop(); // Clear any existing timers
    
    // Set up message listener
    const subscription = this.client.on('message', (message) => {
      if (message.type === 'heartbeat_ack') {
        this.handleHeartbeatResponse(message as ServerHeartbeatAckMessage);
      }
    });

    // Start sending heartbeats
    this.sendHeartbeat();
    this.intervalId = window.setInterval(() => this.sendHeartbeat(), this.options.interval);
  }

  public stop(): void {
    this.logger.info('Stopping heartbeat monitoring');
    
    if (this.intervalId !== null) {
      window.clearInterval(this.intervalId);
      this.intervalId = null;
    }
    
    if (this.timeoutId !== null) {
      window.clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
  }

  public on<T extends keyof typeof this.events.events>(
    event: T,
    callback: (data: typeof this.events.events[T]) => void
  ): { unsubscribe: () => void } {
    return this.events.on(event, callback);
  }

  private sendHeartbeat(): void {
    if (this.client.getCurrentStatus() !== ConnectionStatus.CONNECTED) {
      this.logger.debug('Skipping heartbeat: client not connected');
      return;
    }

    const timestamp = Date.now();
    this.lastTimestamp = timestamp;
    
    const message: any = {
      type: 'heartbeat',
      timestamp,
      deviceId: DeviceIdManager.getInstance().getDeviceId(),
    };

    this.logger.debug('Sending heartbeat');
    
    try {
      this.client.send(message);
      
      // Set timeout for response
      if (this.timeoutId !== null) {
        window.clearTimeout(this.timeoutId);
        this.timeoutId = null;
      }
      
      this.timeoutId = window.setTimeout(() => this.handleTimeout(), this.options.timeout);
      
    } catch (error: any) {
      this.logger.error('Failed to send heartbeat', {
        error: error instanceof Error ? error.message : String(error)
      });
    }
  }

  private handleHeartbeatResponse(message: ServerHeartbeatAckMessage): void {
    const now = Date.now();
    const latency = message.clientTimestamp ? (now - message.clientTimestamp) : -1;
    
    this.logger.debug('Heartbeat acknowledged', { latency });
    
    // Clear timeout
    if (this.timeoutId !== null) {
      window.clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
    
    // Check device ID validity
    if (!message.deviceIdValid) {
      this.logger.warn(`Device ID invalidated in heartbeat. Reason: ${message.reason}`);
      this.events.emit('deviceIdInvalidated', {
        deviceId: DeviceIdManager.getInstance().getDeviceId(),
        reason: message.reason
      });
      return;
    }
    
    // Update connection state
    const quality = this.calculateConnectionQuality(latency);
    this.stateManager.updateConnectionState({
      lastHeartbeatTime: now,
      heartbeatLatency: latency >= 0 ? latency : null,
      quality,
      simulatorStatus: message.simulatorStatus
    });
    
    // Emit response event
    this.events.emit('response', message);
  }

  private calculateConnectionQuality(latency: number): string {
    if (latency < 0) return 'UNKNOWN';
    if (latency <= 250) return 'GOOD';
    if (latency <= 750) return 'DEGRADED';
    return 'POOR';
  }

  private handleTimeout(): void {
    this.logger.error(`Heartbeat timeout after ${this.options.timeout}ms`);
    this.timeoutId = null;
    this.events.emit('timeout', undefined);
  }

  public dispose(): void {
    this.stop();
    this.events.clear();
  }
}