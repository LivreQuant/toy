var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g;
    return g = { next: verb(0), "throw": verb(1), "return": verb(2) }, typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (g && (g = 0, op[0] && (_ = 0)), _) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
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
var Resilience = /** @class */ (function () {
    function Resilience(tokenManager, toastService, options) {
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
        this.options = __assign(__assign({}, Resilience.DEFAULT_OPTIONS), (options || {}));
        this.logger.info('Resilience initialized', { options: this.options });
    }
    Resilience.prototype.getState = function () {
        return {
            state: this.state,
            attempt: this.reconnectAttempt,
            failureCount: this.failureCount
        };
    };
    Resilience.prototype.on = function (event, callback) {
        return this.events.on(event, callback);
    };
    Resilience.prototype.recordFailure = function (errorInfo) {
        if (this.isDisposed || this.state === ResilienceState.SUSPENDED || this.state === ResilienceState.FAILED) {
            this.logger.debug("Failure recording skipped in state: ".concat(this.state));
            return;
        }
        this.failureCount++;
        this.lastFailureTime = Date.now();
        this.logger.warn("Connection failure recorded (".concat(this.failureCount, "/").concat(this.options.failureThreshold, ")"), {
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
    };
    Resilience.prototype.attemptReconnection = function (connectCallback) {
        return __awaiter(this, void 0, void 0, function () {
            var delay;
            var _this = this;
            return __generator(this, function (_a) {
                if (this.isDisposed || this.state === ResilienceState.SUSPENDED || this.state === ResilienceState.FAILED) {
                    this.logger.warn("Reconnection attempt cancelled: State is ".concat(this.state));
                    return [2 /*return*/, false];
                }
                if (this.reconnectTimer !== null) {
                    this.logger.warn('Reconnection attempt cancelled: Already scheduled');
                    return [2 /*return*/, true];
                }
                if (!this.tokenManager.isAuthenticated()) {
                    this.logger.error('Reconnection attempt cancelled: Not authenticated');
                    this.reset();
                    return [2 /*return*/, false];
                }
                if (this.reconnectAttempt >= this.options.maxAttempts) {
                    this.logger.error("Maximum reconnection attempts (".concat(this.options.maxAttempts, ") reached."));
                    this.transitionToState(ResilienceState.FAILED, 'Max attempts reached');
                    return [2 /*return*/, false];
                }
                this.transitionToState(ResilienceState.RECOVERING, 'Starting recovery attempt');
                this.reconnectAttempt++;
                delay = this.calculateBackoffDelay();
                this.logger.info("Scheduling reconnection attempt ".concat(this.reconnectAttempt, "/").concat(this.options.maxAttempts, " in ").concat(delay, "ms"));
                this.events.emit('reconnect_scheduled', {
                    attempt: this.reconnectAttempt,
                    maxAttempts: this.options.maxAttempts,
                    delay: delay,
                    when: Date.now() + delay
                });
                this.reconnectTimer = window.setTimeout(function () {
                    _this.executeReconnectAttempt(connectCallback);
                }, delay);
                return [2 /*return*/, true];
            });
        });
    };
    Resilience.prototype.reset = function () {
        this.logger.info('Manual reset called');
        this.stopTimers();
        this.failureCount = 0;
        this.reconnectAttempt = 0;
        var changed = this.state !== ResilienceState.STABLE;
        this.transitionToState(ResilienceState.STABLE, 'Manual reset or successful connection');
        if (changed) {
            this.events.emit('reset', undefined);
        }
    };
    Resilience.prototype.updateAuthState = function (isAuthenticated) {
        if (this.isDisposed)
            return;
        if (!isAuthenticated && this.state !== ResilienceState.STABLE) {
            this.logger.info('Authentication lost, resetting resilience state');
            this.reset();
        }
    };
    Resilience.prototype.executeReconnectAttempt = function (connectCallback) {
        return __awaiter(this, void 0, void 0, function () {
            var connected, successfulAttempt, error_1;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0:
                        this.reconnectTimer = null;
                        if (this.isDisposed ||
                            this.state !== ResilienceState.RECOVERING ||
                            !this.tokenManager.isAuthenticated()) {
                            this.logger.warn("Reconnect execution skipped: Disposed, state changed (".concat(this.state, "), or logged out"));
                            if (this.state !== ResilienceState.RECOVERING && !this.isDisposed) {
                                this.reset();
                            }
                            return [2 /*return*/];
                        }
                        this.logger.info("Executing reconnection attempt ".concat(this.reconnectAttempt));
                        this.events.emit('reconnect_attempt', {
                            attempt: this.reconnectAttempt,
                            maxAttempts: this.options.maxAttempts
                        });
                        _a.label = 1;
                    case 1:
                        _a.trys.push([1, 3, , 4]);
                        return [4 /*yield*/, connectCallback()];
                    case 2:
                        connected = _a.sent();
                        if (this.isDisposed)
                            return [2 /*return*/];
                        if (connected) {
                            this.logger.info("Reconnection attempt ".concat(this.reconnectAttempt, " successful"));
                            this.transitionToState(ResilienceState.STABLE, 'Reconnection successful');
                            this.failureCount = 0;
                            successfulAttempt = this.reconnectAttempt;
                            this.reconnectAttempt = 0;
                            this.events.emit('reconnect_success', { attempt: successfulAttempt });
                        }
                        else {
                            this.logger.warn("Reconnection attempt ".concat(this.reconnectAttempt, " failed"));
                            this.events.emit('reconnect_failure', { attempt: this.reconnectAttempt });
                            this.recordFailure("Reconnection attempt ".concat(this.reconnectAttempt, " failed"));
                            if (this.state === ResilienceState.RECOVERING) {
                                this.attemptReconnection(connectCallback);
                            }
                        }
                        return [3 /*break*/, 4];
                    case 3:
                        error_1 = _a.sent();
                        if (this.isDisposed)
                            return [2 /*return*/];
                        this.logger.error("Exception during reconnection attempt ".concat(this.reconnectAttempt), {
                            error: error_1 instanceof Error ? error_1.message : String(error_1)
                        });
                        this.events.emit('reconnect_failure', {
                            attempt: this.reconnectAttempt,
                            error: error_1
                        });
                        this.recordFailure(error_1 instanceof Error ? error_1 : new Error(String(error_1)));
                        if (this.state === ResilienceState.RECOVERING) {
                            this.attemptReconnection(connectCallback);
                        }
                        return [3 /*break*/, 4];
                    case 4: return [2 /*return*/];
                }
            });
        });
    };
    Resilience.prototype.calculateBackoffDelay = function () {
        var baseDelay = Math.min(this.options.maxDelayMs, this.options.initialDelayMs * Math.pow(2, this.reconnectAttempt - 1));
        var jitterRange = this.options.jitterFactor * baseDelay;
        return Math.max(0, Math.floor(baseDelay + (Math.random() * jitterRange * 2) - jitterRange));
    };
    Resilience.prototype.transitionToState = function (newState, reason) {
        var oldState = this.state;
        if (oldState === newState)
            return;
        this.state = newState;
        this.logger.warn("State transitioned: ".concat(oldState, " -> ").concat(newState, " (Reason: ").concat(reason, ")"));
        this.events.emit('state_changed', {
            oldState: oldState,
            newState: newState,
            reason: reason
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
    };
    Resilience.prototype.enterSuspendedStateLogic = function () {
        var _this = this;
        this.stopTimers();
        this.suspensionTimer = window.setTimeout(function () {
            _this.exitSuspendedState();
        }, this.options.suspensionTimeoutMs);
        this.events.emit('suspended', {
            failureCount: this.failureCount,
            resumeTime: Date.now() + this.options.suspensionTimeoutMs
        });
    };
    Resilience.prototype.exitSuspendedState = function () {
        if (this.state !== ResilienceState.SUSPENDED || this.isDisposed)
            return;
        this.logger.info('Exiting SUSPENDED state. Connection attempts can now resume');
        this.suspensionTimer = null;
        this.failureCount = 0;
        this.reconnectAttempt = 0;
        this.transitionToState(ResilienceState.STABLE, 'Suspension ended');
        this.events.emit('resumed', undefined);
    };
    Resilience.prototype.enterFailedStateLogic = function () {
        this.stopTimers();
        this.events.emit('max_attempts_reached', {
            attempts: this.reconnectAttempt,
            maxAttempts: this.options.maxAttempts
        });
    };
    Resilience.prototype.stopTimers = function () {
        if (this.reconnectTimer !== null) {
            window.clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.suspensionTimer !== null) {
            window.clearTimeout(this.suspensionTimer);
            this.suspensionTimer = null;
        }
    };
    Resilience.prototype.dispose = function () {
        if (this.isDisposed)
            return;
        this.isDisposed = true;
        this.logger.info('Disposing Resilience');
        this.stopTimers();
        this.events.clear();
    };
    Resilience.DEFAULT_OPTIONS = {
        initialDelayMs: 1000,
        maxDelayMs: 30000,
        maxAttempts: 10,
        suspensionTimeoutMs: 60000,
        failureThreshold: 5,
        jitterFactor: 0.3
    };
    return Resilience;
}());
export { Resilience };
