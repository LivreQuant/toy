// src/services/connection/recovery-manager.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { ConnectionRecoveryInterface } from './connection-recovery-interface';
import { 
  UnifiedConnectionState, 
  ConnectionServiceType, 
  ConnectionStatus 
} from './unified-connection-state';

export enum RecoveryState {
  IDLE = 'idle',
  ATTEMPTING = 'attempting',
  SUCCEEDED = 'succeeded',
  FAILED = 'failed'
}

export class RecoveryManager extends EventEmitter {
  private connectionManager: ConnectionRecoveryInterface;
  private tokenManager: TokenManager;
  private unifiedState: UnifiedConnectionState;
  private recoveryAttempts: number = 0;
  private maxRecoveryAttempts: number = 3;
  private recoveryTimer: number | null = null;
  private recoveryState: RecoveryState = RecoveryState.IDLE;

  constructor(
    connectionManager: ConnectionRecoveryInterface, 
    tokenManager: TokenManager,
    unifiedState: UnifiedConnectionState
  ) {
    super();
    this.connectionManager = connectionManager;
    this.tokenManager = tokenManager;
    this.unifiedState = unifiedState;
  }

  public dispose(): void {
    if (this.recoveryTimer) {
      window.clearTimeout(this.recoveryTimer);
      this.recoveryTimer = null;
    }
    
    // Clean up all event listeners
    super.dispose();
  }
  
  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
    // Authentication check
    if (!this.tokenManager.isAuthenticated()) {
      console.warn('Cannot recover connection - not authenticated');
      return false;
    }

    const state = this.connectionManager.getState();
    
    // Prevent unnecessary recovery attempts if already connected
    if (state.isConnected) {
      console.log('Already connected, skipping recovery');
      return true;
    }

    // Don't allow multiple concurrent recovery attempts
    if (this.recoveryState === RecoveryState.ATTEMPTING) {
      console.log('Recovery already in progress');
      return false;
    }

    // Limit recovery attempts
    if (this.recoveryAttempts >= this.maxRecoveryAttempts) {
      console.warn('Max recovery attempts reached');
      this.emit('recovery_failed');
      this.unifiedState.updateRecovery(false, this.recoveryAttempts);
      return false;
    }

    // Start recovery process
    this.recoveryState = RecoveryState.ATTEMPTING;
    this.recoveryAttempts++;
    console.log(`Attempting connection recovery (${this.recoveryAttempts}/${this.maxRecoveryAttempts}), reason: ${reason}`);
    
    // Update unified state
    this.unifiedState.updateRecovery(true, this.recoveryAttempts);
    
    // Emit recovery attempt event
    this.emit('recovery_attempt', { 
      attempt: this.recoveryAttempts,
      maxAttempts: this.maxRecoveryAttempts,
      reason
    });

    try {
      // First disconnect completely to ensure clean reconnection
      this.connectionManager.disconnect();
      
      // Then reconnect
      const reconnected = await this.connectionManager.connect();
      
      if (reconnected) {
        // Success - reset state
        this.recoveryAttempts = 0;
        this.recoveryState = RecoveryState.SUCCEEDED;
        this.unifiedState.updateRecovery(false, 0);
        this.emit('recovery_success');
        return true;
      }

      // If reconnection fails, use exponential backoff for next attempt
      this.recoveryState = RecoveryState.FAILED;
      const delay = Math.min(30000, Math.pow(2, this.recoveryAttempts) * 1000);
      
      // Update unified state
      this.unifiedState.updateRecovery(true, this.recoveryAttempts);
      
      this.recoveryTimer = window.setTimeout(() => {
        this.recoveryState = RecoveryState.IDLE;
        this.attemptRecovery('scheduled_retry');
      }, delay);

      return false;
    } catch (error) {
      console.error('Recovery attempt failed:', error);
      this.recoveryState = RecoveryState.FAILED;
      this.unifiedState.updateRecovery(false, this.recoveryAttempts);
      this.emit('recovery_failed');
      return false;
    }
  }

  // Handle authentication state changes
  public updateAuthState(isAuthenticated: boolean): void {
    if (!isAuthenticated) {
      // Clear any recovery attempts if user is no longer authenticated
      this.dispose();
      this.recoveryAttempts = 0;
      this.recoveryState = RecoveryState.IDLE;
      this.unifiedState.updateRecovery(false, 0);
    }
  }
}