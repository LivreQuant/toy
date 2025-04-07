// src/services/connection/connection-resilience-manager.ts
import { TypedEventEmitter, EventMap } from '../../utils/typed-event-emitter';
import { EnhancedLogger } from '../../utils/enhanced-logger';
import { TokenManager } from '../auth/token-manager';
import { AppErrorHandler } from '../../utils/app-error-handler';
import { ErrorSeverity } from '../../utils/error-handler';
import { Disposable } from '../../utils/disposable';

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
  suspensionTimeoutMs?: number; // Correct name
  failureThreshold?: number;
  jitterFactor?: number;
}

export interface ResilienceEvents extends EventMap {
    failure_recorded: { count: number; threshold: number; state: ResilienceState; error?: any };
    state_changed: { oldState: ResilienceState; newState: ResilienceState; reason: string };
    suspended: { failureCount: number; resumeTime: number };
    resumed: void; // Payload is void
    reset: void; // Payload is void
    reconnect_scheduled: { attempt: number; maxAttempts: number; delay: number; when: number };
    reconnect_attempt: { attempt: number; maxAttempts: number };
    reconnect_success: { attempt: number };
    reconnect_failure: { attempt: number; error?: any };
    max_attempts_reached: { attempts: number; maxAttempts: number };
}


export class ConnectionResilienceManager extends TypedEventEmitter<ResilienceEvents> implements Disposable {
  private state: ResilienceState = ResilienceState.STABLE;
  private tokenManager: TokenManager;
  private logger: EnhancedLogger;
  private reconnectAttempt: number = 0;
  private failureCount: number = 0;
  private lastFailureTime: number = 0;
  private reconnectTimer: number | null = null;
  private suspensionTimer: number | null = null;
  public readonly options: Required<ResilienceOptions>;
  private isDisposed: boolean = false;

  private static DEFAULT_OPTIONS: Required<ResilienceOptions> = {
    initialDelayMs: 1000,
    maxDelayMs: 30000,
    maxAttempts: 10,
    suspensionTimeoutMs: 60000, // Correct name
    failureThreshold: 5,
    jitterFactor: 0.3
  };

  constructor(
    tokenManager: TokenManager,
    parentLogger: EnhancedLogger,
    options?: ResilienceOptions // Accept ResilienceOptions directly
  ) {
    super('ResilienceManagerEvents');
    this.tokenManager = tokenManager;
    this.logger = parentLogger.createChild('ResilienceManager');
    // Merge provided options ensuring correct types
    this.options = {
      ...ConnectionResilienceManager.DEFAULT_OPTIONS,
      ...(options || {}) // Ensure options is not undefined
    };
    this.logger.info('Resilience manager initialized', { options: this.options });
  }


  public getState(): { state: ResilienceState; attempt: number; failureCount: number; } {
    return { state: this.state, attempt: this.reconnectAttempt, failureCount: this.failureCount };
  }


  public recordFailure(errorInfo?: any): void {
    if (this.isDisposed || this.state === ResilienceState.SUSPENDED || this.state === ResilienceState.FAILED) {
        this.logger.debug(`Failure recording skipped in state: ${this.state}`);
        return;
    }

    this.failureCount++;
    this.lastFailureTime = Date.now();
    this.logger.warn(`Connection failure recorded (${this.failureCount}/${this.options.failureThreshold})`, { error: errorInfo });

    this.emit('failure_recorded', {
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

    this.emit('reconnect_scheduled', {
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
    this.logger.info('Manual reset called.');
    this.stopTimers();
    this.failureCount = 0;
    this.reconnectAttempt = 0;
    const changed = this.state !== ResilienceState.STABLE; // Check if state actually changes
    this.transitionToState(ResilienceState.STABLE, 'Manual reset or successful connection');
    // FIX: Pass undefined for void payload
    if (changed) this.emit('reset', undefined); // Only emit reset event if state was not already stable
  }


  public updateAuthState(isAuthenticated: boolean): void {
    if (this.isDisposed) return;
    if (!isAuthenticated && this.state !== ResilienceState.STABLE) {
       this.logger.info('Authentication lost, resetting resilience state.');
       this.reset();
    }
  }


  private async executeReconnectAttempt(connectCallback: () => Promise<boolean>): Promise<void> {
      this.reconnectTimer = null;

      if (this.isDisposed || this.state !== ResilienceState.RECOVERING || !this.tokenManager.isAuthenticated()) {
          this.logger.warn(`Reconnect execution skipped: Disposed, state changed (${this.state}), or logged out.`);
          if (this.state !== ResilienceState.RECOVERING && !this.isDisposed) this.reset();
          return;
       }

      this.logger.info(`Executing reconnection attempt ${this.reconnectAttempt}`);
      this.emit('reconnect_attempt', { attempt: this.reconnectAttempt, maxAttempts: this.options.maxAttempts });

      try {
          const connected = await connectCallback();
          if (this.isDisposed) return;

          if (connected) {
              this.logger.info(`Reconnection attempt ${this.reconnectAttempt} successful.`);
              this.transitionToState(ResilienceState.STABLE, 'Reconnection successful');
              this.failureCount = 0;
              const successfulAttempt = this.reconnectAttempt; // Capture attempt number before reset
              this.reconnectAttempt = 0;
              this.emit('reconnect_success', { attempt: successfulAttempt });
          } else {
              this.logger.warn(`Reconnection attempt ${this.reconnectAttempt} failed.`);
              this.emit('reconnect_failure', { attempt: this.reconnectAttempt });
              this.recordFailure(`Reconnection attempt ${this.reconnectAttempt} failed.`);
              if (this.state === ResilienceState.RECOVERING) {
                 this.attemptReconnection(connectCallback);
              }
          }
      } catch (error: any) {
           if (this.isDisposed) return;
           this.logger.error(`Exception during reconnection attempt ${this.reconnectAttempt}`, { error: error.message });
           this.emit('reconnect_failure', { attempt: this.reconnectAttempt, error });
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
      const delay = Math.max(0, Math.floor(baseDelay + (Math.random() * jitterRange * 2) - jitterRange));
      return delay;
  }


  private transitionToState(newState: ResilienceState, reason: string): void {
      const oldState = this.state;
      if (oldState === newState) return;

      this.state = newState;
      this.logger.warn(`State transitioned: ${oldState} -> ${newState} (Reason: ${reason})`);
      this.emit('state_changed', { oldState, newState, reason });

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
               this.stopTimers(); // Ensure any timers are cleared
               break;
          case ResilienceState.RECOVERING:
                // Reset failure count when starting recovery? Or keep it? Decide policy.
                // Keeping it allows triggering suspension even during recovery attempts.
                // this.failureCount = 0; // Optional reset here
                this.stopTimers(); // Stop suspension timer if it was running
                break;
      }
  }


  private enterSuspendedStateLogic(): void {
      this.stopTimers();
      AppErrorHandler.handleConnectionError(
          `Connection attempts suspended for ${this.options.suspensionTimeoutMs / 1000}s after ${this.failureCount} failures.`,
          ErrorSeverity.HIGH,
          'ConnectionResilience'
      );
      this.suspensionTimer = window.setTimeout(() => {
          this.exitSuspendedState();
      }, this.options.suspensionTimeoutMs);
      this.emit('suspended', {
          failureCount: this.failureCount,
          resumeTime: Date.now() + this.options.suspensionTimeoutMs
      });
  }


   private exitSuspendedState(): void {
       if (this.state !== ResilienceState.SUSPENDED || this.isDisposed) return;
       this.logger.info('Exiting SUSPENDED state. Connection attempts can now resume.');
       this.suspensionTimer = null;
       this.failureCount = 0;
       this.reconnectAttempt = 0;
       this.transitionToState(ResilienceState.STABLE, 'Suspension ended');
       // FIX: Pass undefined for void payload
       this.emit('resumed', undefined);
   }


  private enterFailedStateLogic(): void {
      this.stopTimers();
       AppErrorHandler.handleConnectionError(
          `Failed to establish connection after ${this.options.maxAttempts} attempts. Manual intervention may be required.`,
          ErrorSeverity.FATAL,
          'ConnectionResilience'
       );
      this.emit('max_attempts_reached', {
        attempts: this.reconnectAttempt,
        maxAttempts: this.options.maxAttempts
      });
  }


  private stopTimers(): void {
      let timerCleared = false;
      if (this.reconnectTimer !== null) {
          window.clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
          timerCleared = true;
      }
      if (this.suspensionTimer !== null) {
          window.clearTimeout(this.suspensionTimer);
          this.suspensionTimer = null;
          timerCleared = true;
      }
      if(timerCleared) this.logger.debug('Cleared active timers.');
  }


  public dispose(): void {
    if (this.isDisposed) return;
    this.isDisposed = true;
    this.logger.info('Disposing ConnectionResilienceManager...');
    this.stopTimers();
    this.removeAllListeners();
    this.logger.info('ConnectionResilienceManager disposed.');
  }

  [Symbol.dispose](): void {
    this.dispose();
  }
}