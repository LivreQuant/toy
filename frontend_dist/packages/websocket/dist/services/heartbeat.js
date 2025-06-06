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
// src/services/heartbeat.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { EventEmitter } from '@trading-app/utils';
var Heartbeat = /** @class */ (function () {
    function Heartbeat(client, stateManager, options) {
        var _this = this;
        this.client = client;
        this.stateManager = stateManager;
        this.logger = getLogger('Heartbeat');
        this.heartbeatIntervalId = null;
        this.heartbeatTimeoutId = null;
        this.isStarted = false;
        this.isDisposed = false;
        this.lastHeartbeatTimestamp = 0;
        this.events = new EventEmitter();
        var defaultOptions = {
            interval: 15000,
            timeout: 5000
        };
        this.options = __assign(__assign({}, defaultOptions), (options || {}));
        this.logger.info('Heartbeat initialized', { options: this.options });
        this.client.on('message', function (message) {
            if (message.type === 'heartbeat_ack') {
                _this.handleHeartbeatResponse(message);
            }
        });
    }
    Heartbeat.prototype.isActive = function () {
        return this.isStarted && !this.isDisposed;
    };
    Heartbeat.prototype.start = function () {
        if (this.isStarted || this.isDisposed) {
            this.logger.debug('Heartbeat start ignored: Already started or disposed');
            return;
        }
        this.logger.info('Starting heartbeats...');
        this.isStarted = true;
        this.sendHeartbeat();
        this.scheduleNextHeartbeat();
    };
    Heartbeat.prototype.stop = function () {
        if (!this.isStarted || this.isDisposed) {
            this.logger.debug('Heartbeat stop ignored: Not running or disposed');
            return;
        }
        this.logger.info('Stopping heartbeats...');
        this.isStarted = false;
        this.clearHeartbeatInterval();
        this.clearHeartbeatTimeout();
    };
    Heartbeat.prototype.on = function (event, callback) {
        return this.events.on(event, callback);
    };
    Heartbeat.prototype.scheduleNextHeartbeat = function () {
        var _this = this;
        this.clearHeartbeatInterval();
        this.heartbeatIntervalId = window.setInterval(function () {
            _this.sendHeartbeat();
        }, this.options.interval);
    };
    Heartbeat.prototype.sendHeartbeat = function () {
        var _this = this;
        if (!this.isStarted || this.isDisposed)
            return;
        if (this.client.getCurrentStatus() !== ConnectionStatus.CONNECTED) {
            this.logger.debug('Skipping heartbeat: WebSocket not connected');
            return;
        }
        this.logger.debug('Sending heartbeat');
        var heartbeatMsg = {
            type: 'heartbeat',
            timestamp: Date.now(),
            deviceId: DeviceIdManager.getInstance().getDeviceId()
        };
        try {
            this.client.send(heartbeatMsg);
            this.clearHeartbeatTimeout();
            this.heartbeatTimeoutId = window.setTimeout(function () {
                _this.handleHeartbeatTimeout();
            }, this.options.timeout);
        }
        catch (error) {
            this.logger.error('Failed to send heartbeat', {
                error: error instanceof Error ? error.message : String(error)
            });
        }
    };
    Heartbeat.prototype.handleHeartbeatResponse = function (message) {
        this.lastHeartbeatTimestamp = Date.now();
        this.logger.debug('Heartbeat Response Analysis', {
            deviceIdValid: message.deviceIdValid,
            simulatorStatus: message.simulatorStatus,
            clientTimestamp: message.clientTimestamp,
            serverTimestamp: Date.now(),
            latency: message.clientTimestamp ? (Date.now() - message.clientTimestamp) : -1
        });
        this.clearHeartbeatTimeout();
        var latency = message.clientTimestamp ? (Date.now() - message.clientTimestamp) : -1;
        // Update state through injected state manager
        if (latency >= 0) {
            var quality = this.calculateConnectionQuality(latency);
            this.stateManager.updateConnectionState({
                lastHeartbeatTime: Date.now(),
                heartbeatLatency: latency,
                quality: quality,
                simulatorStatus: message.simulatorStatus
            });
        }
        this.events.emit('response', {
            latency: latency,
            deviceIdValid: message.deviceIdValid,
            simulatorStatus: message.simulatorStatus
        });
    };
    Heartbeat.prototype.calculateConnectionQuality = function (latency) {
        if (latency <= 250)
            return 'GOOD';
        if (latency <= 750)
            return 'DEGRADED';
        return 'POOR';
    };
    Heartbeat.prototype.handleHeartbeatTimeout = function () {
        this.logger.error('Heartbeat timeout detected');
        this.events.emit('timeout', undefined);
    };
    Heartbeat.prototype.clearHeartbeatInterval = function () {
        if (this.heartbeatIntervalId !== null) {
            window.clearInterval(this.heartbeatIntervalId);
            this.heartbeatIntervalId = null;
        }
    };
    Heartbeat.prototype.clearHeartbeatTimeout = function () {
        if (this.heartbeatTimeoutId !== null) {
            window.clearTimeout(this.heartbeatTimeoutId);
            this.heartbeatTimeoutId = null;
        }
    };
    Heartbeat.prototype.dispose = function () {
        if (this.isDisposed)
            return;
        this.isDisposed = true;
        this.stop();
        this.events.clear();
        this.logger.info('Heartbeat disposed');
    };
    return Heartbeat;
}());
export { Heartbeat };
