// src/services/websocket/heartbeat-manager.ts
import { WebSocketManager } from './websocket-manager';
import { EnhancedLogger } from '../../utils/enhanced-logger';
import { Disposable } from '../../utils/disposable';
import { getLogger } from '../../boot/logging';
import { appState } from '../state/app-state.service';

import { WebSocketMessage, ServerHeartbeatAckMessage } from './message-types';
import { ConnectionStatus } from '../state/app-state.service';

export interface HeartbeatManagerOptions {
  interval?: number; // How often to send heartbeats (ms)
  timeout?: number;  // How long to wait for response before considering connection dead (ms)
}

export class HeartbeatManager implements Disposable {
  private wsManager: WebSocketManager;
  private options: Required<HeartbeatManagerOptions>;
  private heartbeatIntervalId: number | null = null;
  private heartbeatTimeoutId: number | null = null;
  private isStarted: boolean = false;
  private isDisposed: boolean = false;
  private logger: EnhancedLogger;
  private subscription: any = null;

  private lastHeartbeatTimestamp: number = 0; // Add this property

  constructor(
    wsManager: WebSocketManager,
    options?: HeartbeatManagerOptions
  ) {
    this.wsManager = wsManager;
    this.logger = getLogger('HeartbeatManager');
    
    const defaults: Required<HeartbeatManagerOptions> = {
      interval: 15000, // 15 seconds
      timeout: 5000    // 5 seconds
    };
    
    this.options = { ...defaults, ...(options || {}) };
    this.logger.info('HeartbeatManager initialized', { options: this.options });
  }

  public start(): void {
    if (this.isStarted || this.isDisposed) return;
    this.logger.info('Starting heartbeats...');
    this.isStarted = true;
    this.scheduleNextHeartbeat();
    
    // Subscribe to heartbeat_ack messages
    this.subscription = this.wsManager.on('heartbeat_ack').subscribe(message => {
      if (this.isDisposed || !this.isStarted) return;
      this.clearHeartbeatTimeout();
      this.logger.debug('Heartbeat acknowledged', { 
        latency: Date.now() - message.clientTimestamp 
      });
    });
  }

  public stop(): void {
    if (!this.isStarted) return;
    this.logger.info('Stopping heartbeats...');
    this.isStarted = false;
    this.clearHeartbeatInterval();
    this.clearHeartbeatTimeout();
    
    if (this.subscription) {
      this.subscription.unsubscribe();
      this.subscription = null;
    }
  }

  private scheduleNextHeartbeat(): void {
    this.clearHeartbeatInterval();
    this.heartbeatIntervalId = window.setInterval(() => {
      this.sendHeartbeat();
    }, this.options.interval);
  }

  private sendHeartbeat(): void {
    if (!this.isStarted || this.isDisposed) return;
    
    this.logger.debug('Sending heartbeat');
    this.wsManager.sendHeartbeat();
    
    // Set timeout for heartbeat acknowledgment
    this.clearHeartbeatTimeout();
    this.heartbeatTimeoutId = window.setTimeout(() => {
      this.handleHeartbeatTimeout();
    }, this.options.timeout);
  }

  private handleHeartbeatTimeout(): void {
    this.logger.error('Heartbeat Timeout - Detailed Diagnostics', {
      isStarted: this.isStarted,
      isDisposed: this.isDisposed,
      interval: this.options.interval,
      timeout: this.options.timeout,
      lastHeartbeatTimestamp: this.lastHeartbeatTimestamp,
      currentTime: Date.now(),
      timeSinceLastHeartbeat: Date.now() - this.lastHeartbeatTimestamp
    });

    if (!this.isStarted || this.isDisposed) return;
    this.logger.error(`Heartbeat timeout after ${this.options.timeout}ms`);
    
    // Stop sending heartbeats
    this.stop();
    
    // Notify WebSocketManager that connection is dead
    if (this.wsManager) {
      this.logger.warn('Triggering WebSocket disconnect due to heartbeat timeout');
      this.wsManager.disconnect('heartbeat_timeout');
    }
  }

  public handleHeartbeatResponse(message: ServerHeartbeatAckMessage): void {
    this.lastHeartbeatTimestamp = Date.now();
    
    this.logger.debug('Heartbeat Response Analysis', {
      deviceIdValid: message.deviceIdValid,
      simulatorStatus: message.simulatorStatus,
      clientTimestamp: message.clientTimestamp,
      serverTimestamp: Date.now(),
      latency: message.clientTimestamp ? (Date.now() - message.clientTimestamp) : -1
    });

    // This method is kept for backward compatibility
    this.clearHeartbeatTimeout();
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
    this.logger.info('HeartbeatManager disposed');
  }

  [Symbol.dispose](): void {
    this.dispose();
  }
}