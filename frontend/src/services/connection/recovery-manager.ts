// src/services/connection/recovery-manager.ts

import { EventEmitter } from '../../utils/event-emitter';
import { SessionStore } from '../session/session-store';

export enum RecoveryState {
  IDLE = 'idle',
  ATTEMPTING = 'attempting',
  SUCCEEDED = 'succeeded',
  FAILED = 'failed'
}

export class RecoveryManager extends EventEmitter {
  private connectionManager: any; // Using 'any' to avoid circular dependency
  private recoveryState: RecoveryState = RecoveryState.IDLE;
  private recoveryAttempts: number = 0;
  private maxRecoveryAttempts: number = 5;
  private recoveryTimer: number | null = null;
  private networkOnlineHandler: () => void;
  private networkOfflineHandler: () => void;
  private visibilityChangeHandler: () => void;
  private focusHandler: () => void;
  private sessionUpdateHandler: () => void;
  
  constructor(connectionManager: any) {
    super();
    this.connectionManager = connectionManager;
    
    // Set up event handlers
    this.networkOnlineHandler = this.handleNetworkOnline.bind(this);
    this.networkOfflineHandler = this.handleNetworkOffline.bind(this);
    this.visibilityChangeHandler = this.handleVisibilityChange.bind(this);
    this.focusHandler = this.handleFocus.bind(this);
    
    // Set up listeners
    window.addEventListener('online', this.networkOnlineHandler);
    window.addEventListener('offline', this.networkOfflineHandler);
    document.addEventListener('visibilitychange', this.visibilityChangeHandler);
    window.addEventListener('focus', this.focusHandler);
    
    // Listen for connection state changes
    this.connectionManager.on('state_change', this.handleConnectionStateChange.bind(this));
  }
  
  public dispose(): void {
    // Remove all event listeners
    window.removeEventListener('online', this.networkOnlineHandler);
    window.removeEventListener('offline', this.networkOfflineHandler);
    document.removeEventListener('visibilitychange', this.visibilityChangeHandler);
    window.removeEventListener('focus', this.focusHandler);
    
    if (this.recoveryTimer) {
      window.clearTimeout(this.recoveryTimer);
      this.recoveryTimer = null;
    }
  }
  
  // Handle network coming back online
  private handleNetworkOnline(): void {
    console.log('Network came online, attempting connection recovery');
    this.attemptRecovery('network_online');
  }
  
  // Handle network going offline
  private handleNetworkOffline(): void {
    console.log('Network went offline');
    // We don't need to do anything here, the WebSocket will detect disconnection
    this.emit('network_offline');
  }
  
  // Handle tab becoming visible again
  private handleVisibilityChange(): void {
    if (document.visibilityState === 'visible') {
      console.log('Tab became visible, checking connection');
      this.checkConnection();
    }
  }
  
  // Handle window focus event
  private handleFocus(): void {
    console.log('Window gained focus, checking connection');
    this.checkConnection();
  }
  
  // Check if connection is still valid
  private async checkConnection(): void {
    const state = this.connectionManager.getState();
    
    if (!state.isConnected) {
      // We're disconnected, try to recover
      this.attemptRecovery('connection_check');
      return;
    }
    
    // We appear to be connected, but let's verify with a heartbeat
    try {
      const sent = this.connectionManager.wsManager?.send({ 
        type: 'heartbeat', 
        timestamp: Date.now() 
      });
      
      if (!sent) {
        // Couldn't send heartbeat, connection might be dead
        console.log('Failed to send heartbeat, connection might be dead');
        this.attemptRecovery('failed_heartbeat');
      }
    } catch (error) {
      console.error('Error sending heartbeat check', error);
      this.attemptRecovery('heartbeat_error');
    }
  }
  
  // Handle connection state changes
  private handleConnectionStateChange(data: { previous: any, current: any }): void {
    const { previous, current } = data;
    
    // If we just connected, reset recovery state
    if (!previous.isConnected && current.isConnected) {
      this.recoveryState = RecoveryState.IDLE;
      this.recoveryAttempts = 0;
      this.emit('recovery_reset');
    }
    
    // If we just disconnected, attempt recovery
    if (previous.isConnected && !current.isConnected) {
      this.attemptRecovery('connection_lost');
    }
  }
  
  // Main recovery logic
  public async attemptRecovery(reason: string): Promise<boolean> {
    if (this.recoveryState === RecoveryState.ATTEMPTING) {
      console.log('Recovery already in progress, skipping new attempt');
      return false;
    }
    
    this.recoveryState = RecoveryState.ATTEMPTING;
    this.recoveryAttempts++;
    
    console.log(`Attempting connection recovery (${this.recoveryAttempts}/${this.maxRecoveryAttempts}), reason: ${reason}`);
    
    this.emit('recovery_attempt', { 
      attempt: this.recoveryAttempts, 
      maxAttempts: this.maxRecoveryAttempts,
      reason
    });
    
    try {
      // Try standard reconnection first
      const reconnected = await this.connectionManager.reconnect();
      
      if (reconnected) {
        this.recoveryState = RecoveryState.SUCCEEDED;
        this.emit('recovery_success', { attempt: this.recoveryAttempts });
        return true;
      }
      
      // If we reach here, reconnection failed
      console.log('Standard reconnection failed');
      
      if (this.recoveryAttempts >= this.maxRecoveryAttempts) {
        this.recoveryState = RecoveryState.FAILED;
        this.emit('recovery_failed', { maxAttemptsReached: true });
        return false;
      }
      
      // Schedule another attempt with backoff
      const delay = Math.min(30000, Math.pow(2, this.recoveryAttempts) * 1000);
      console.log(`Scheduling next recovery attempt in ${delay}ms`);
      
      this.recoveryTimer = window.setTimeout(() => {
        this.recoveryState = RecoveryState.IDLE;
        this.attemptRecovery('scheduled_retry');
      }, delay);
      
      return false;
    } catch (error) {
      console.error('Error during recovery attempt', error);
      this.recoveryState = RecoveryState.FAILED;
      this.emit('recovery_error', { error });
      return false;
    }
  }
}