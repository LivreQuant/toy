// src/services/connection/connection-resilience-manager.ts
import { EventEmitter } from '../../utils/event-emitter';
import { Logger } from '../../utils/logger';
import { TokenManager } from '../auth/token-manager';
import { AppErrorHandler } from '../../utils/app-error-handler';
import { ErrorSeverity } from '../../utils/error-handler';

// Connection resilience states
export enum ResilienceState {
  STABLE = 'stable',          // Normal operation
  DEGRADED = 'degraded',      // Some recoverable errors
  RECOVERING = 'recovering',  // Actively attempting to recover
  SUSPENDED = 'suspended',    // Temporarily suspended due to repeated failures
  FAILED = 'failed'           // Failed to recover after max attempts
}

export interface ResilienceOptions {
  initialDelayMs?: number;       // Initial backoff delay (ms)
  maxDelayMs?: number;           // Maximum backoff delay (ms)
  maxAttempts?: number;          // Maximum recovery attempts
  resetTimeoutMs?: number;       // Time after which to reset failure count (ms)
  failureThreshold?: number;     // Failures before entering SUSPENDED state
  jitterFactor?: number;         // Random factor for backoff (0-1)
}

export class ConnectionResilienceManager extends EventEmitter {
  private state: ResilienceState = ResilienceState.STABLE;
  private tokenManager: TokenManager;
  private logger: Logger;
  private reconnectAttempt: number = 0;
  private failureCount: number = 0;
  private lastFailureTime: number = 0;
  private reconnectTimer: number | null = null;
  private suspensionTimer: number | null = null;
  private options: Required<ResilienceOptions>;
  private isDisposed: boolean = false;
  
  // Default options
  private static DEFAULT_OPTIONS: Required<ResilienceOptions> = {
    initialDelayMs: 1000,     // 1 second
    maxDelayMs: 30000,        // 30 seconds
    maxAttempts: 10,          // 10 attempts
    resetTimeoutMs: 60000,    // 1 minute
    failureThreshold: 5,      // 5 failures
    jitterFactor: 0.3         // 30% jitter
  };
  
  constructor(
    tokenManager: TokenManager,
    logger: Logger,
    options?: ResilienceOptions
  ) {
    super();
    
    this.tokenManager = tokenManager;
    this.logger = logger.createChild('ResilienceManager');
    this.options = {
      ...ConnectionResilienceManager.DEFAULT_OPTIONS,
      ...options
    };
    
    this.logger.info('Resilience manager initialized', { options: this.options });
  }
  
  /**
   * Gets the current resilience state
   */
  public getState(): {
    state: ResilienceState;
    attempt: number;
    maxAttempts: number;
    failureCount: number;
    failureThreshold: number;
  } {
    return {
      state: this.state,
      attempt: this.reconnectAttempt,
      maxAttempts: this.options.maxAttempts,
      failureCount: this.failureCount,
      failureThreshold: this.options.failureThreshold
    };
  }
  
  /**
   * Records a connection failure and manages state transitions
   */
  public recordFailure(errorInfo?: any): void {
    if (this.isDisposed) return;
    
    this.failureCount++;
    this.lastFailureTime = Date.now();
    
    this.logger.warn(`Connection failure recorded (${this.failureCount}/${this.options.failureThreshold})`, errorInfo);
    
    // Check if we need to suspend recovery attempts due to repeated failures
    if (this.failureCount >= this.options.failureThreshold) {
      this.enterSuspendedState();
    }
    
    this.emit('failure', {
      count: this.failureCount,
      threshold: this.options.failureThreshold,
      state: this.state,
      error: errorInfo
    });
  }
  
  /**
   * Enters the SUSPENDED state where connection attempts are temporarily paused
   */
  private enterSuspendedState(): void {
    if (this.state === ResilienceState.SUSPENDED) return;
    
    this.stopTimers();
    this.state = ResilienceState.SUSPENDED;
    this.logger.error(`Entering SUSPENDED state due to repeated failures (${this.failureCount}). Pausing reconnection attempts for ${this.options.resetTimeoutMs}ms.`);
    
    AppErrorHandler.handleConnectionError(
      `Connection attempts temporarily suspended after ${this.failureCount} failures.`,
      ErrorSeverity.HIGH,
      'ConnectionResilience'
    );
    
    // Schedule a timer to exit the suspended state
    this.suspensionTimer = window.setTimeout(() => {
      this.exitSuspendedState();
    }, this.options.resetTimeoutMs);
    
    this.emit('suspended', {
      failureCount: this.failureCount,
      resumeTime: Date.now() + this.options.resetTimeoutMs
    });
  }
  
  /**
   * Exits the SUSPENDED state, allowing connection attempts to resume
   */
  private exitSuspendedState(): void {
    if (this.state !== ResilienceState.SUSPENDED) return;
    
    this.state = ResilienceState.STABLE;
    this.failureCount = 0;
    this.reconnectAttempt = 0;
    this.suspensionTimer = null;
    
    this.logger.info('Exiting SUSPENDED state. Connection attempts can now resume.');
    
    this.emit('resumed', {
      message: 'Connection attempts can now resume.'
    });
  }
  
  /**
   * Manually resets the resilience state, clearing all counters and timers
   */
  public reset(): void {
    this.stopTimers();
    this.state = ResilienceState.STABLE;
    this.failureCount = 0;
    this.reconnectAttempt = 0;
    this.logger.info('Resilience state manually reset.');
    this.emit('reset');
  }
  
  /**
   * Starts the reconnection process with exponential backoff
   * @param connectCallback - Function to call when attempting reconnection
   * @returns Promise resolving to whether reconnection should be attempted
   */
  public async attemptReconnection(
    connectCallback: () => Promise<boolean>
  ): Promise<boolean> {
    if (this.isDisposed) {
      this.logger.warn('Reconnection attempt canceled: manager is disposed');
      return false;
    }
    
    // Check if in a state where reconnection is not allowed
    if (this.state === ResilienceState.SUSPENDED) {
      this.logger.warn('Reconnection attempt canceled: currently in SUSPENDED state');
      return false;
    }
    
    // Check if reconnection is already in progress
    if (this.state === ResilienceState.RECOVERING) {
      this.logger.warn('Reconnection already in progress');
      return false;
    }
    
    // Check authentication
    if (!this.tokenManager.isAuthenticated()) {
      this.logger.error('Reconnection attempt canceled: not authenticated');
      return false;
    }
    
    // Check max attempts
    if (this.reconnectAttempt >= this.options.maxAttempts) {
      this.state = ResilienceState.FAILED;
      this.logger.error(`Maximum reconnection attempts (${this.options.maxAttempts}) reached`);
      
      AppErrorHandler.handleConnectionError(
        `Failed to reconnect after ${this.options.maxAttempts} attempts.`,
        ErrorSeverity.HIGH,
        'ConnectionResilience'
      );
      
      this.emit('max_attempts_reached', {
        attempts: this.reconnectAttempt,
        maxAttempts: this.options.maxAttempts
      });
      
      return false;
    }
    
    // Enter recovering state
    this.state = ResilienceState.RECOVERING;
    this.reconnectAttempt++;
    
    // Calculate backoff delay with jitter
    const baseDelay = Math.min(
      this.options.maxDelayMs,
      this.options.initialDelayMs * Math.pow(2, this.reconnectAttempt - 1)
    );
    
    const jitter = 1 - this.options.jitterFactor + (Math.random() * this.options.jitterFactor * 2);
    const delay = Math.floor(baseDelay * jitter);
    
    this.logger.info(`Scheduling reconnection attempt ${this.reconnectAttempt}/${this.options.maxAttempts} in ${delay}ms`);
    
    this.emit('reconnect_scheduled', {
      attempt: this.reconnectAttempt,
      maxAttempts: this.options.maxAttempts,
      delay,
      when: Date.now() + delay
    });
    
    // Return a promise that resolves after the backoff period
    return new Promise((resolve) => {
      this.reconnectTimer = window.setTimeout(async () => {
        this.reconnectTimer = null;
        
        // Check if we're still authenticated and not disposed
        if (this.isDisposed || !this.tokenManager.isAuthenticated()) {
          this.logger.warn('Reconnection canceled: disposed or not authenticated');
          resolve(false);
          return;
        }
        
        this.logger.info(`Executing reconnection attempt ${this.reconnectAttempt}`);
        
        try {
          // Execute the provided connect callback
          const connected = await connectCallback();
          
          if (connected) {
            this.state = ResilienceState.STABLE;
            this.failureCount = 0;
            this.reconnectAttempt = 0;
            this.logger.info('Reconnection successful');
            this.emit('reconnect_success');
          } else {
            this.logger.warn(`Reconnection attempt ${this.reconnectAttempt} failed`);
            this.emit('reconnect_failure', {
              attempt: this.reconnectAttempt,
              maxAttempts: this.options.maxAttempts
            });
          }
          
          resolve(connected);
        } catch (error) {
          this.logger.error(`Error during reconnection attempt`, { error });
          this.recordFailure(error);
          resolve(false);
        }
      }, delay);
    });
  }
  
  /**
   * Handles authentication state changes
   * @param isAuthenticated - Whether the user is currently authenticated
   */
  public updateAuthState(isAuthenticated: boolean): void {
    if (this.isDisposed) return;
    
    if (!isAuthenticated) {
      this.stopTimers();
      this.state = ResilienceState.STABLE;
      this.failureCount = 0;
      this.reconnectAttempt = 0;
      this.logger.info('Authentication lost, resetting reconnection state');
    }
  }
  
  /**
   * Stops all active timers
   */
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
  
  /**
   * Performs cleanup when the manager is no longer needed
   */
  public dispose(): void {
    if (this.isDisposed) return;
    
    this.isDisposed = true;
    this.stopTimers();
    this.removeAllListeners();
    this.logger.info('Connection resilience manager disposed');
  }
}