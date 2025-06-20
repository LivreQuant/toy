// src/services/heartbeat.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { Disposable, EventEmitter } from '@trading-app/utils';

import { SocketClient } from '../client/socket-client';
import { HeartbeatOptions, StateManager } from '../types/connection-types';

export class Heartbeat implements Disposable {
  private logger = getLogger('Heartbeat');
  private heartbeatIntervalId: number | null = null;
  private heartbeatTimeoutId: number | null = null;
  private isStarted: boolean = false;
  private isDisposed: boolean = false;
  private lastHeartbeatTimestamp: number = 0;
  
  private events = new EventEmitter<{
    timeout: void;
    response: { latency: number; deviceIdValid: boolean; simulatorStatus: string };
  }>();

  private options: Required<HeartbeatOptions>;

  constructor(
    private client: SocketClient,
    private stateManager: StateManager,
    options?: Partial<HeartbeatOptions>
  ) {
    const defaultOptions: Required<HeartbeatOptions> = {
      interval: 15000,
      timeout: 5000
    };
    
    this.options = { ...defaultOptions, ...(options || {}) };
    this.logger.info('Heartbeat initialized', { options: this.options });
    
    this.client.on('message', (message) => {
      if (message.type === 'heartbeat_ack') {
        this.handleHeartbeatResponse(message);
      }
    });
  }

  public isActive(): boolean {
    return this.isStarted && !this.isDisposed;
  }

  public start(): void {
    if (this.isStarted || this.isDisposed) {
      this.logger.debug('Heartbeat start ignored: Already started or disposed');
      return;
    }
    
    this.logger.info('Starting heartbeats...');
    this.isStarted = true;
    
    this.sendHeartbeat();
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

  public on<T extends keyof {
    timeout: void;
    response: { latency: number; deviceIdValid: boolean; simulatorStatus: string };
  }>(
    event: T,
    callback: (data: T extends 'timeout' ? void : 
                   { latency: number; deviceIdValid: boolean; simulatorStatus: string }) => void
  ): { unsubscribe: () => void } {
    return this.events.on(event as any, callback as any);
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
    
    this.clearHeartbeatTimeout();
    
    const latency = message.clientTimestamp ? (Date.now() - message.clientTimestamp) : -1;
    
    // Update state through injected state manager
    if (latency >= 0) {
      const quality = this.calculateConnectionQuality(latency);
      this.stateManager.updateConnectionState({
        lastHeartbeatTime: Date.now(),
        heartbeatLatency: latency,
        quality,
        simulatorStatus: message.simulatorStatus
      });
    }
    
    this.events.emit('response', {
      latency,
      deviceIdValid: message.deviceIdValid,
      simulatorStatus: message.simulatorStatus
    });
  }

  private calculateConnectionQuality(latency: number): string {
    if (latency <= 250) return 'GOOD';
    if (latency <= 750) return 'DEGRADED';
    return 'POOR';
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

}