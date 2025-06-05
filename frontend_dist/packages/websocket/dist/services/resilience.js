// src/services/resilience.ts
import { getLogger } from '@trading-app/logging';
import { EventEmitter } from '@trading-app/utils';
export var ResilienceState;
(function (ResilienceState) {
    ResilienceState["STABLE"] = "stable";
    ResilienceState["DEGRADED"] = "degraded";
    ResilienceState["RECOVERING"] = "recovering";
    ResilienceState["SUSPENDED"] = "suspended";
    ResilienceState["FAILED"] = "failed";
})(ResilienceState || (ResilienceState = {}));
export class Resilience {
    constructor(tokenManager, toastService, options) {
        this.tokenManager = tokenManager;
        this.toastService = toastService;
        this.logger = getLogger('Resilience');
        this.state = ResilienceState.STABLE;
        this.reconnectAttempt = 0;
        this.failureCount = 0;
        this.lastFailureTime = 0;
        this.reconnectTimer = null;
        this.suspensionTimer = null;
        this.isDisposed = false;
        this.events = new EventEmitter();
        this.options = { ...Resilience.DEFAULT_OPTIONS, ...(options || {}) };
        this.logger.info('Resilience initialized', { options: this.options });
    }
    getState() {
        return {
            state: this.state,
            attempt: this.reconnectAttempt,
            failureCount: this.failureCount
        };
    }
    on(event, callback) {
        return this.events.on(event, callback);
    }
    recordFailure(errorInfo) {
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
    async attemptReconnection(connectCallback) {
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
    reset() {
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
    updateAuthState(isAuthenticated) {
        if (this.isDisposed)
            return;
        if (!isAuthenticated && this.state !== ResilienceState.STABLE) {
            this.logger.info('Authentication lost, resetting resilience state');
            this.reset();
        }
    }
    async executeReconnectAttempt(connectCallback) {
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
            if (this.isDisposed)
                return;
            if (connected) {
                this.logger.info(`Reconnection attempt ${this.reconnectAttempt} successful`);
                this.transitionToState(ResilienceState.STABLE, 'Reconnection successful');
                this.failureCount = 0;
                const successfulAttempt = this.reconnectAttempt;
                this.reconnectAttempt = 0;
                this.events.emit('reconnect_success', { attempt: successfulAttempt });
            }
            else {
                this.logger.warn(`Reconnection attempt ${this.reconnectAttempt} failed`);
                this.events.emit('reconnect_failure', { attempt: this.reconnectAttempt });
                this.recordFailure(`Reconnection attempt ${this.reconnectAttempt} failed`);
                if (this.state === ResilienceState.RECOVERING) {
                    this.attemptReconnection(connectCallback);
                }
            }
        }
        catch (error) {
            if (this.isDisposed)
                return;
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
    calculateBackoffDelay() {
        const baseDelay = Math.min(this.options.maxDelayMs, this.options.initialDelayMs * Math.pow(2, this.reconnectAttempt - 1));
        const jitterRange = this.options.jitterFactor * baseDelay;
        return Math.max(0, Math.floor(baseDelay + (Math.random() * jitterRange * 2) - jitterRange));
    }
    transitionToState(newState, reason) {
        const oldState = this.state;
        if (oldState === newState)
            return;
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
                this.failureCount = 0;
                this.reconnectAttempt = 0;
                this.stopTimers();
                break;
            case ResilienceState.RECOVERING:
                this.stopTimers();
                break;
        }
    }
    enterSuspendedStateLogic() {
        this.stopTimers();
        this.suspensionTimer = window.setTimeout(() => {
            this.exitSuspendedState();
        }, this.options.suspensionTimeoutMs);
        this.events.emit('suspended', {
            failureCount: this.failureCount,
            resumeTime: Date.now() + this.options.suspensionTimeoutMs
        });
    }
    exitSuspendedState() {
        if (this.state !== ResilienceState.SUSPENDED || this.isDisposed)
            return;
        this.logger.info('Exiting SUSPENDED state. Connection attempts can now resume');
        this.suspensionTimer = null;
        this.failureCount = 0;
        this.reconnectAttempt = 0;
        this.transitionToState(ResilienceState.STABLE, 'Suspension ended');
        this.events.emit('resumed', undefined);
    }
    enterFailedStateLogic() {
        this.stopTimers();
        this.events.emit('max_attempts_reached', {
            attempts: this.reconnectAttempt,
            maxAttempts: this.options.maxAttempts
        });
    }
    stopTimers() {
        if (this.reconnectTimer !== null) {
            window.clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.suspensionTimer !== null) {
            window.clearTimeout(this.suspensionTimer);
            this.suspensionTimer = null;
        }
    }
    dispose() {
        if (this.isDisposed)
            return;
        this.isDisposed = true;
        this.logger.info('Disposing Resilience');
        this.stopTimers();
        this.events.clear();
    }
}
Resilience.DEFAULT_OPTIONS = {
    initialDelayMs: 1000,
    maxDelayMs: 30000,
    maxAttempts: 10,
    suspensionTimeoutMs: 60000,
    failureThreshold: 5,
    jitterFactor: 0.3
};
