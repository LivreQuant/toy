// src/services/connection/resilience.ts
import { getLogger } from '../../boot/logging';

import { TokenManager } from '../auth/token-manager';

import { Disposable } from '../../utils/disposable';
import { EventEmitter } from '../../utils/events';

export enum ResilienceState {
  STABLE = 'stable',
  DEGRADED = 'degraded',
  RECOVERING = 'recovering',
  SUSPENDED = 'suspended',
  FAILED = 'failed'
}

export interface ResilienceOptions {
  initialDelayMs?: number;
  maxDelayMs?: number;
  maxAttempts?: number;
  suspensionTimeoutMs?: number;
  failureThreshold?: number;
  jitterFactor?: number;
}

export class Resilience implements Disposable {
  private logger = getLogger('Resilience');
  
  private tokenManager: TokenManager;
  private state: ResilienceState = ResilienceState.STABLE;
  private reconnectAttempt: number = 0;
  private failureCount: number = 0;
  private lastFailureTime: number = 0;
  private reconnectTimer: number | null = null;
  private suspensionTimer: number | null = null;
  private isDisposed: boolean = false;
  
  public readonly options: Required<ResilienceOptions>;
  
  private events = new EventEmitter<{
    failure_recorded: { count: number; threshold: number; state: ResilienceState; error?: any };
    state_changed: { oldState: ResilienceState; newState: ResilienceState; reason: string };
    suspended: { failureCount: number; resumeTime: number };
    resumed: void;
    reset: void;
    reconnect_scheduled: { attempt: number; maxAttempts: number; delay: number; when: number };
    reconnect_attempt: { attempt: number; maxAttempts: number };
    reconnect_success: { attempt: number };
    reconnect_failure: { attempt: number; error?: any };
    max_attempts_reached: { attempts: number; maxAttempts: number };
  }>();

  private static DEFAULT_OPTIONS: Required<ResilienceOptions> = {
    initialDelayMs: 1000,
    maxDelayMs: 30000,
    maxAttempts: 10,
    suspensionTimeoutMs: 60000,
    failureThreshold: 5,
    jitterFactor: 0.3
  };

  constructor(
    tokenManager: TokenManager,
    options?: ResilienceOptions
  ) {
    this.tokenManager = tokenManager;
    this.options = { ...Resilience.DEFAULT_OPTIONS, ...(options || {}) };
    this.logger.info('Resilience initialized', { options: this.options });
  }

  public getState(): { state: ResilienceState; attempt: number; failureCount: number } {
    return {
      state: this.state,
      attempt: this.reconnectAttempt,
      failureCount: this.failureCount
    };
  }

  public on<T extends keyof typeof this.events.events>(
    event: T,
    callback: (data: typeof this.events.events[T]) => void
  ): { unsubscribe: () => void } {
    return this.events.on(event, callback);
  }

  public recordFailure(errorInfo?: any): void {
    if (this.isDisposed || this.state === ResilienceState.SUSPENDED || this.state === ResilienceState.FAILED) {
      this.logger.debug(`Failure recording skipped in state: ${this.state}`);
      return;
    }

    this.failureCount++;
    this.lastFailureTime = Date.now();
    
    this.logger.warn(`Connection failure recorded (${this.failureCount}/${this.options.failureThreshold})`, {
      error: errorInfo
    });

    this.events.emit('failure_recorded', {
      count: this.failureCount,
      threshold: this.options.failureThreshold,
      state: this.state,
      error: errorInfo
    });

    if (this.failureCount >= this.options.failureThreshold && this.state !== ResilienceState.RECOVERING) {
      this.transitionToState(ResilienceState.SUSPENDED, 'Failure threshold reached');
    }
  }

  public async attemptReconnection(connectCallback: () => Promise<boolean>): Promise<boolean> {
    if (this.isDisposed || this.state === ResilienceState.SUSPENDED || this.state === ResilienceState.FAILED) {
      this.logger.warn(`Reconnection attempt cancelled: State is ${this.state}`);
      return false;
    }
    
    if (this.reconnectTimer !== null) {
      this.logger.warn('Reconnection attempt cancelled: Already scheduled');
      return true;
    }
    
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.error('Reconnection attempt cancelled: Not authenticated');
      this.reset();
      return false;
    }

    if (this.reconnectAttempt >= this.options.maxAttempts) {
      this.logger.error(`Maximum reconnection attempts (${this.options.maxAttempts}) reached.`);
      this.transitionToState(ResilienceState.FAILED, 'Max attempts reached');
      return false;
    }

    this.transitionToState(ResilienceState.RECOVERING, 'Starting recovery attempt');
    this.reconnectAttempt++;

    const delay = this.calculateBackoffDelay();
    
    this.logger.info(`Scheduling reconnection attempt ${this.reconnectAttempt}/${this.options.maxAttempts} in ${delay}ms`);

    this.events.emit('reconnect_scheduled', {
      attempt: this.reconnectAttempt,
      maxAttempts: this.options.maxAttempts,
      delay,
      when: Date.now() + delay
    });

    this.reconnectTimer = window.setTimeout(() => {
      this.executeReconnectAttempt(connectCallback);
    }, delay);

    return true;
  }

  public reset(): void {
    this.logger.info('Manual reset called');
    this.stopTimers();
    this.failureCount = 0;
    this.reconnectAttempt = 0;
    
    const changed = this.state !== ResilienceState.STABLE;
    this.transitionToState(ResilienceState.STABLE, 'Manual reset or successful connection');
    
    if (changed) {
      this.events.emit('reset', undefined);
    }
  }

  public updateAuthState(isAuthenticated: boolean): void {
    if (this.isDisposed) return;
    
    if (!isAuthenticated && this.state !== ResilienceState.STABLE) {
      this.logger.info('Authentication lost, resetting resilience state');
      this.reset();
    }
  }

  private async executeReconnectAttempt(connectCallback: () => Promise<boolean>): Promise<void> {
    this.reconnectTimer = null;

    if (this.isDisposed || 
        this.state !== ResilienceState.RECOVERING || 
        !this.tokenManager.isAuthenticated()) {
      this.logger.warn(`Reconnect execution skipped: Disposed, state changed (${this.state}), or logged out`);
      if (this.state !== ResilienceState.RECOVERING && !this.isDisposed) {
        this.reset();
      }
      return;
    }

    this.logger.info(`Executing reconnection attempt ${this.reconnectAttempt}`);
    
    this.events.emit('reconnect_attempt', {
      attempt: this.reconnectAttempt,
      maxAttempts: this.options.maxAttempts
    });

    try {
      const connected = await connectCallback();
      
      if (this.isDisposed) return;

      if (connected) {
        this.logger.info(`Reconnection attempt ${this.reconnectAttempt} successful`);
        this.transitionToState(ResilienceState.STABLE, 'Reconnection successful');
        this.failureCount = 0;
        
        const successfulAttempt = this.reconnectAttempt;
        this.reconnectAttempt = 0;
        
        this.events.emit('reconnect_success', { attempt: successfulAttempt });
      } else {
        this.logger.warn(`Reconnection attempt ${this.reconnectAttempt} failed`);
        
        this.events.emit('reconnect_failure', { attempt: this.reconnectAttempt });
        this.recordFailure(`Reconnection attempt ${this.reconnectAttempt} failed`);
        
        if (this.state === ResilienceState.RECOVERING) {
          this.attemptReconnection(connectCallback);
        }
      }
    } catch (error: any) {
      if (this.isDisposed) return;
      
      this.logger.error(`Exception during reconnection attempt ${this.reconnectAttempt}`, {
        error: error instanceof Error ? error.message : String(error)
      });
      
      this.events.emit('reconnect_failure', {
        attempt: this.reconnectAttempt,
        error
      });
      
      this.recordFailure(error instanceof Error ? error : new Error(String(error)));
      
      if (this.state === ResilienceState.RECOVERING) {
        this.attemptReconnection(connectCallback);
      }
    }
  }

  private calculateBackoffDelay(): number {
    const baseDelay = Math.min(
      this.options.maxDelayMs,
      this.options.initialDelayMs * Math.pow(2, this.reconnectAttempt - 1)
    );
    
    const jitterRange = this.options.jitterFactor * baseDelay;
    
    return Math.max(0, Math.floor(
      baseDelay + (Math.random() * jitterRange * 2) - jitterRange
    ));
  }

  private transitionToState(newState: ResilienceState, reason: string): void {
    const oldState = this.state;
    if (oldState === newState) return;

    this.state = newState;
    
    this.logger.warn(`State transitioned: ${oldState} -> ${newState} (Reason: ${reason})`);
    
    this.events.emit('state_changed', {
      oldState,
      newState,
      reason
    });

    switch (newState) {
      case ResilienceState.SUSPENDED:
        this.enterSuspendedStateLogic();
        break;
      case ResilienceState.FAILED:
        this.enterFailedStateLogic();
        break;
      case ResilienceState.STABLE:
        // Reset counters when explicitly transitioning TO stable
        this.failureCount = 0;
        this.reconnectAttempt = 0;
        this.stopTimers();
        break;
      case ResilienceState.RECOVERING:
        // Stop suspension timer if it was running
        this.stopTimers();
        break;
    }
  }

  private enterSuspendedStateLogic(): void {
    this.stopTimers();
    
    this.suspensionTimer = window.setTimeout(() => {
      this.exitSuspendedState();
    }, this.options.suspensionTimeoutMs);
    
    this.events.emit('suspended', {
      failureCount: this.failureCount,
      resumeTime: Date.now() + this.options.suspensionTimeoutMs
    });
  }

  private exitSuspendedState(): void {
    if (this.state !== ResilienceState.SUSPENDED || this.isDisposed) return;
    
    this.logger.info('Exiting SUSPENDED state. Connection attempts can now resume');
    this.suspensionTimer = null;
    this.failureCount = 0;
    this.reconnectAttempt = 0;
    
    this.transitionToState(ResilienceState.STABLE, 'Suspension ended');
    this.events.emit('resumed', undefined);
  }

  private enterFailedStateLogic(): void {
    this.stopTimers();
    
    this.events.emit('max_attempts_reached', {
      attempts: this.reconnectAttempt,
      maxAttempts: this.options.maxAttempts
    });
  }

  private stopTimers(): void {
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
    if (this.suspensionTimer !== null) {
      window.clearTimeout(this.suspensionTimer);
      this.suspensionTimer = null;
    }
  }

  public dispose(): void {
    if (this.isDisposed) return;
    this.isDisposed = true;
    
    this.logger.info('Disposing Resilience');
    this.stopTimers();
    this.events.clear();
  }

  [Symbol.dispose](): void {
    this.dispose();
  }
}