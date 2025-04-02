// src/services/connection/recovery-manager.ts

import { EventEmitter } from '../../utils/event-emitter';
import { SessionStore } from '../session/session-manager';
import { TokenManager } from '../auth/token-manager';

export enum RecoveryState {
  IDLE = 'idle',
  ATTEMPTING = 'attempting',
  SUCCEEDED = 'succeeded',
  FAILED = 'failed'
}

// src/services/connection/recovery-manager.ts
export class RecoveryManager extends EventEmitter {
  private connectionManager: any;
  private tokenManager: TokenManager;
  private recoveryAttempts: number = 0;
  private maxRecoveryAttempts: number = 3;
  private recoveryTimer: number | null = null;

  constructor(connectionManager: any, tokenManager: TokenManager) {
    super();
    this.connectionManager = connectionManager;
    this.tokenManager = tokenManager;
  }

  public dispose(): void {
    if (this.recoveryTimer) {
      window.clearTimeout(this.recoveryTimer);
      this.recoveryTimer = null;
    }
  }

  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    // Authentication and connection state checks
    if (!this.tokenManager.isAuthenticated()) {
      console.warn('Cannot recover connection - not authenticated');
      return false;
    }

    const state = this.connectionManager.getState();
    
    // Prevent unnecessary recovery attempts
    if (state.isConnected) {
      console.log('Already connected, skipping recovery');
      return true;
    }

    // Limit recovery attempts
    if (this.recoveryAttempts >= this.maxRecoveryAttempts) {
      console.warn('Max recovery attempts reached');
      return false;
    }

    this.recoveryAttempts++;
    console.log(`Attempting connection recovery (${this.recoveryAttempts}/${this.maxRecoveryAttempts}), reason: ${reason}`);

    try {
      const reconnected = await this.connectionManager.connect();
      
      if (reconnected) {
        this.recoveryAttempts = 0; // Reset attempts on success
        return true;
      }

      // If reconnection fails, use exponential backoff
      const delay = Math.min(30000, Math.pow(2, this.recoveryAttempts) * 1000);
      
      this.recoveryTimer = window.setTimeout(() => {
        this.attemptRecovery('scheduled_retry');
      }, delay);

      return false;
    } catch (error) {
      console.error('Recovery attempt failed:', error);
      return false;
    }
  }

  // Minimal auth state management
  public updateAuthState(isAuthenticated: boolean): void {
    if (!isAuthenticated) {
      this.connectionManager.disconnect();
      this.recoveryAttempts = 0;
    }
  }
}