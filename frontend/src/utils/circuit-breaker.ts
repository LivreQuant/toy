// src/utils/circuit-breaker.ts
import { getLogger } from '../boot/logging'; // Use your logger
import { EnhancedLogger } from './enhanced-logger'; // Or './logger'

export enum CircuitState {
  CLOSED = "CLOSED",         // Normal operation, requests allowed
  OPEN = "OPEN",             // Requests fail fast, waiting for timeout
  HALF_OPEN = "HALF_OPEN"    // Allowing a limited number of test requests
}

// Optional configuration for the circuit breaker
export interface CircuitBreakerOptions {
  failureThreshold?: number;    // Number of failures to trip the circuit
  resetTimeoutMs?: number;      // Time in ms before transitioning from OPEN to HALF_OPEN
  maxHalfOpenCalls?: number;    // Max number of requests allowed in HALF_OPEN state
  // Add successThreshold for HALF_OPEN? (e.g., require N successes to close)
  // successThresholdHalfOpen?: number;
}

// Type for the state change listener callback
export type StateChangeListener = (
    name: string,
    oldState: CircuitState,
    newState: CircuitState,
    details: any // Contextual details about the transition
) => void;


export class CircuitBreaker {
  private state: CircuitState = CircuitState.CLOSED;
  private failureCount: number = 0;
  private lastFailureTime: number = 0; // Timestamp of the last recorded failure
  private halfOpenCallCount: number = 0; // Counter for calls made in HALF_OPEN state
  // private halfOpenSuccessCount: number = 0; // Counter for successful calls in HALF_OPEN

  // Configuration with defaults
  private readonly failureThreshold: number;
  private readonly resetTimeout: number;
  private readonly maxHalfOpenCalls: number;
  // private readonly successThresholdHalfOpen: number;

  // Listeners for state changes
  private stateChangeListeners: Array<StateChangeListener> = [];

  // Naming and logging
  private readonly name: string;
  private readonly logger: EnhancedLogger;

  constructor(
      name: string,
      options: CircuitBreakerOptions = {},
      parentLogger?: EnhancedLogger // Optional parent logger
    ) {
    this.name = name;
    // Use provided logger or get a default one
    this.logger = (parentLogger || getLogger('CircuitBreaker')).createChild(name);

    // Set configuration using defaults
    this.failureThreshold = options.failureThreshold ?? 5;
    this.resetTimeout = options.resetTimeoutMs ?? 30000; // Default 30 seconds
    this.maxHalfOpenCalls = options.maxHalfOpenCalls ?? 1; // Default to 1 test call
    // this.successThresholdHalfOpen = options.successThresholdHalfOpen ?? 1;

     if (this.maxHalfOpenCalls <= 0) {
         this.logger.warn("maxHalfOpenCalls must be positive, defaulting to 1");
         this.maxHalfOpenCalls = 1;
     }

    this.logger.info('Circuit Breaker initialized', {
        failureThreshold: this.failureThreshold,
        resetTimeout: this.resetTimeout,
        maxHalfOpenCalls: this.maxHalfOpenCalls,
    });
  }

  /**
   * Executes the given asynchronous function, protected by the circuit breaker logic.
   * @param fn The async function to execute.
   * @returns A promise that resolves with the result of `fn` or rejects if the circuit is open or `fn` fails.
   */
  public async execute<T>(fn: () => Promise<T>): Promise<T> {
    this.logger.debug(`Executing function. Current state: ${this.state}`);

    if (this.state === CircuitState.OPEN) {
      return this.handleOpenState(); // Check if ready for HALF_OPEN or fail fast
    }

    if (this.state === CircuitState.HALF_OPEN) {
      return this.handleHalfOpenState(fn); // Allow limited calls and check result
    }

    // --- State is CLOSED ---
    try {
      const result = await fn();
      // Success in CLOSED state: reset failure count if it was > 0
      this.recordSuccess();
      return result;
    } catch (error: any) {
      // Failure in CLOSED state: record failure and potentially trip
      this.recordFailure(error);
      throw error; // Re-throw the original error
    }
  }

  // --- State Handling Logic ---

  private async handleOpenState<T>(): Promise<T> {
      const now = Date.now();
      const timeSinceFailure = now - this.lastFailureTime;

      // Check if the reset timeout has elapsed
      if (timeSinceFailure > this.resetTimeout) {
        this.logger.warn(`Reset timeout elapsed (${timeSinceFailure}ms > ${this.resetTimeout}ms). Transitioning to HALF_OPEN.`);
        this.transitionState(CircuitState.HALF_OPEN, {
          reason: "Reset timeout elapsed",
          timeSinceLastFailure: timeSinceFailure
        });
        // Immediately throw after transitioning? Or allow first call?
        // Current implementation transitions *before* allowing a call in execute()
        // Re-throwing here ensures the *current* call fails fast even if we just transitioned.
         throw new Error(`Circuit "${this.name}" is now HALF_OPEN, retry shortly.`);
      } else {
        // Circuit is still open, fail fast
        const timeLeft = this.resetTimeout - timeSinceFailure;
        this.logger.debug(`Circuit OPEN. Failing fast. ${timeLeft.toFixed(0)}ms until potential HALF_OPEN.`);
        throw new Error(`Circuit "${this.name}" is OPEN. Requests blocked for approx ${Math.round(timeLeft / 1000)} more seconds.`);
      }
  }

  private async handleHalfOpenState<T>(fn: () => Promise<T>): Promise<T> {
     // Check concurrency limit for HALF_OPEN calls
     if (this.halfOpenCallCount >= this.maxHalfOpenCalls) {
         this.logger.warn(`Circuit HALF_OPEN call limit (${this.maxHalfOpenCalls}) reached. Failing fast.`);
         throw new Error(`Circuit "${this.name}" is HALF_OPEN and testing capacity reached.`);
     }

     // Increment the counter for the current test call
     this.halfOpenCallCount++;
     this.logger.info(`Circuit HALF_OPEN: Allowing test call (${this.halfOpenCallCount}/${this.maxHalfOpenCalls}).`);


     try {
         const result = await fn();
         // --- Test call SUCCEEDED ---
         // Logic for closing the circuit after successful test(s)
         // Simple: If one succeeds, close immediately
         this.logger.info(`Circuit HALF_OPEN: Test call successful. Resetting circuit to CLOSED.`);
         this.reset(); // Reset closes the circuit and clears counters
         return result;

         // More complex logic (e.g., require N successes):
         // this.halfOpenSuccessCount++;
         // if (this.halfOpenSuccessCount >= this.successThresholdHalfOpen) {
         //     this.logger.info(`Circuit HALF_OPEN: Success threshold reached (${this.halfOpenSuccessCount}). Resetting circuit to CLOSED.`);
         //     this.reset();
         // } else {
         //     this.logger.info(`Circuit HALF_OPEN: Test call successful (${this.halfOpenSuccessCount}/${this.successThresholdHalfOpen}). State remains HALF_OPEN.`);
         // }
         // return result;

     } catch (error: any) {
         // --- Test call FAILED ---
         this.logger.error(`Circuit HALF_OPEN: Test call failed. Re-opening circuit.`, { error: error.message });
         this.transitionState(CircuitState.OPEN, {
           reason: "Test call failed in HALF_OPEN state",
           error: error instanceof Error ? error.message : String(error)
         });
         throw error; // Re-throw the original error that caused the test failure
     } finally {
        // Decrement counter *after* call completes (success or failure)
        // This logic might need adjustment depending on desired concurrency handling.
        // If we decrement immediately, another call might slip in before the result is known.
        // Decrementing here means the slot is occupied until the async operation finishes.
         // this.halfOpenCallCount = Math.max(0, this.halfOpenCallCount - 1); // Decrement might happen too early here
         // It might be better to handle the counter reset *only* when transitioning state (in reset() or transition to OPEN)
     }
  }

  // --- Success/Failure Recording ---

  private recordSuccess(): void {
    if (this.failureCount > 0) {
      this.logger.info(`Request successful in CLOSED state. Resetting failure count from ${this.failureCount} to 0.`);
      this.failureCount = 0; // Reset failure count on success
    }
     // No state transition needed if already CLOSED
  }

  private recordFailure(error: any): void {
      this.failureCount++;
      this.lastFailureTime = Date.now();
      this.logger.warn(`Failure recorded in CLOSED state (${this.failureCount}/${this.failureThreshold}).`, { error: error.message });


      // Check if failure threshold is met to trip the circuit
      if (this.failureCount >= this.failureThreshold) {
        this.logger.error(`Failure threshold (${this.failureThreshold}) exceeded. Tripping circuit to OPEN.`);
        this.transitionState(CircuitState.OPEN, {
          reason: "Failure threshold exceeded",
          failureCount: this.failureCount,
          error: error instanceof Error ? error.message : String(error)
        });
      }
      // State remains CLOSED if threshold not met
  }


  // --- Manual Control and State ---

  /**
   * Manually resets the circuit breaker to the CLOSED state.
   * Clears failure counts and resets timers/counters.
   */
  public reset(): void {
    if (this.state !== CircuitState.CLOSED) { // Only log/emit if state actually changes
        this.logger.warn('Manual reset triggered. Setting state to CLOSED.');
        this.transitionState(CircuitState.CLOSED, { reason: "Manual reset or successful test call" });
    }
    // Always clear counts regardless of previous state
    this.failureCount = 0;
    this.halfOpenCallCount = 0;
    // this.halfOpenSuccessCount = 0;
    this.lastFailureTime = 0; // Reset last failure time as well? Or keep it for info?
  }

  /** Gets the current state of the circuit breaker. */
  public getState(): CircuitState {
    return this.state;
  }

   /** Gets the configured reset timeout in milliseconds. */
   public getResetTimeout(): number {
     return this.resetTimeout;
   }

  // --- Event Listener Management ---

  /**
   * Adds a listener function to be called when the circuit breaker's state changes.
   * @param listener The callback function.
   */
  public onStateChange(listener: StateChangeListener): void {
    this.stateChangeListeners.push(listener);
  }

  /**
   * Removes a previously added state change listener.
   * @param listener The callback function to remove.
   */
  public removeStateChangeListener(listener: StateChangeListener): void {
    this.stateChangeListeners = this.stateChangeListeners.filter(l => l !== listener);
  }

  // --- Internal State Transition ---

  /**
   * Handles the actual state transition and notifies listeners.
   * @param newState The target state.
   * @param details Contextual information about why the state changed.
   */
  private transitionState(newState: CircuitState, details: any): void {
    const oldState = this.state;

    if (oldState === newState) {
      return; // No actual change
    }

    this.state = newState;
    this.logger.warn(`State transitioned: ${oldState} -> ${newState}`, { reason: details.reason });


     // Reset counters when entering specific states
     if (newState === CircuitState.OPEN) {
        this.halfOpenCallCount = 0; // Reset for next HALF_OPEN attempt
        // this.halfOpenSuccessCount = 0;
     } else if (newState === CircuitState.HALF_OPEN) {
         this.halfOpenCallCount = 0; // Reset before allowing test calls
         // this.halfOpenSuccessCount = 0;
     }
     // Resetting to CLOSED is handled in reset()


    // Notify registered listeners
    // Use slice() to prevent issues if a listener modifies the array during iteration
    this.stateChangeListeners.slice().forEach(listener => {
      try {
        listener(this.name, oldState, newState, details);
      } catch (error: any) {
        this.logger.error(`Error in circuit breaker state change listener:`, { listenerName: listener.name, error: error.message });
      }
    });
  }
}