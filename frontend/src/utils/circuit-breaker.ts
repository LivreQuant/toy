
// src/utils/circuit-breaker.ts
export enum CircuitState {
  CLOSED = "CLOSED",         // Normal operation
  OPEN = "OPEN",             // Circuit is open, failing fast
  HALF_OPEN = "HALF_OPEN"    // Testing if service is healthy again
}

export class CircuitBreaker {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount: number = 0;
  private lastFailureTime: number = 0;
  private resetTimeout: number;
  private failureThreshold: number;
  private stateChangeListeners: Array<(name: string, oldState: CircuitState, newState: CircuitState, info: any) => void> = [];
  private halfOpenCallCount: number = 0;
  private maxHalfOpenCalls: number = 1;
  private name: string;
  
  constructor(name: string, failureThreshold: number = 5, resetTimeoutMs: number = 60000, maxHalfOpenCalls: number = 1) {
    this.name = name;
    this.failureThreshold = failureThreshold;
    this.resetTimeout = resetTimeoutMs;
    this.maxHalfOpenCalls = maxHalfOpenCalls;
  }
  
  public async execute<T>(fn: () => Promise<T>): Promise<T> {
    // If circuit is open, fail fast
    if (this.state === CircuitState.OPEN) {
      const now = Date.now();
      
      // Check if it's time to try again
      if (now - this.lastFailureTime > this.resetTimeout) {
        this.transitionState(CircuitState.HALF_OPEN, {
          reason: "Timeout elapsed, testing service",
          timeSinceLastFailure: now - this.lastFailureTime
        });
      } else {
        // Circuit is still open, fail fast
        throw new Error(`Circuit ${this.name} is open`);
      }
    }
    
    // Handle half-open state concurrency limit
    if (this.state === CircuitState.HALF_OPEN) {
      if (this.halfOpenCallCount >= this.maxHalfOpenCalls) {
        throw new Error(`Circuit ${this.name} is half-open and at capacity`);
      }
      
      this.halfOpenCallCount++;
    }
    
    try {
      // Call the function
      const result = await fn();
      
      // Success - reset the circuit if in half-open state
      if (this.state === CircuitState.HALF_OPEN) {
        this.reset();
      } else if (this.state === CircuitState.CLOSED) {
        // In closed state, just reset the failure count
        this.failureCount = 0;
      }
      
      return result;
    } catch (error) {
      // Handle failure based on current state
      this.lastFailureTime = Date.now();
      
      if (this.state === CircuitState.HALF_OPEN) {
        // Failure in half-open state reopens the circuit
        this.transitionState(CircuitState.OPEN, {
          reason: "Failed test call in half-open state",
          error: error instanceof Error ? error.message : String(error)
        });
      } else if (this.state === CircuitState.CLOSED) {
        // In closed state, increment failure count
        this.failureCount++;
        
        // Check if we should trip the circuit
        if (this.failureCount >= this.failureThreshold) {
          this.transitionState(CircuitState.OPEN, {
            reason: "Failure threshold exceeded",
            failureCount: this.failureCount,
            error: error instanceof Error ? error.message : String(error)
          });
        }
      }
      
      // Re-throw the original error
      throw error;
    } finally {
      // If we were in half-open state, decrement the call counter
      if (this.state === CircuitState.HALF_OPEN) {
        this.halfOpenCallCount = Math.max(0, this.halfOpenCallCount - 1);
      }
    }
  }
  
  public reset(): void {
    this.transitionState(CircuitState.CLOSED, {
      reason: "Manual reset or successful test call"
    });
    this.failureCount = 0;
    this.halfOpenCallCount = 0;
  }
  
  public getState(): CircuitState {
    return this.state;
  }
  
  public onStateChange(listener: (name: string, oldState: CircuitState, newState: CircuitState, info: any) => void): void {
    this.stateChangeListeners.push(listener);
  }
  
  private transitionState(newState: CircuitState, stateInfo: any): void {
    const oldState = this.state;
    
    // Only transition if state is different
    if (oldState === newState) {
      return;
    }
    
    this.state = newState;
    
    // Notify listeners
    for (const listener of this.stateChangeListeners) {
      try {
        listener(this.name, oldState, newState, stateInfo);
      } catch (error) {
        console.error(`Error in circuit breaker state change listener:`, error);
      }
    }
  }
}