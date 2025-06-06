// src/handlers/heartbeat-handler.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { EventEmitter } from '@trading-app/utils';
var HeartbeatHandler = /** @class */ (function () {
    function HeartbeatHandler(client, stateManager, options) {
        this.client = client;
        this.stateManager = stateManager;
        this.options = options;
        this.logger = getLogger('HeartbeatHandler');
        this.intervalId = null;
        this.timeoutId = null;
        this.lastTimestamp = 0;
        this.events = new EventEmitter();
        this.logger.info('HeartbeatHandler initialized', { options: options });
    }
    HeartbeatHandler.prototype.start = function () {
        var _this = this;
        this.logger.info('Starting heartbeat monitoring');
        this.stop(); // Clear any existing timers
        // Set up message listener
        var subscription = this.client.on('message', function (message) {
            if (message.type === 'heartbeat_ack') {
                _this.handleHeartbeatResponse(message);
            }
        });
        // Start sending heartbeats
        this.sendHeartbeat();
        this.intervalId = window.setInterval(function () { return _this.sendHeartbeat(); }, this.options.interval);
    };
    HeartbeatHandler.prototype.stop = function () {
        this.logger.info('Stopping heartbeat monitoring');
        if (this.intervalId !== null) {
            window.clearInterval(this.intervalId);
            this.intervalId = null;
        }
        if (this.timeoutId !== null) {
            window.clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }
    };
    HeartbeatHandler.prototype.on = function (event, callback) {
        return this.events.on(event, callback);
    };
    HeartbeatHandler.prototype.sendHeartbeat = function () {
        var _this = this;
        if (this.client.getCurrentStatus() !== ConnectionStatus.CONNECTED) {
            this.logger.debug('Skipping heartbeat: client not connected');
            return;
        }
        var timestamp = Date.now();
        this.lastTimestamp = timestamp;
        var message = {
            type: 'heartbeat',
            timestamp: timestamp,
            deviceId: DeviceIdManager.getInstance().getDeviceId(),
        };
        this.logger.debug('Sending heartbeat');
        try {
            this.client.send(message);
            // Set timeout for response
            if (this.timeoutId !== null) {
                window.clearTimeout(this.timeoutId);
                this.timeoutId = null;
            }
            this.timeoutId = window.setTimeout(function () { return _this.handleTimeout(); }, this.options.timeout);
        }
        catch (error) {
            this.logger.error('Failed to send heartbeat', {
                error: error instanceof Error ? error.message : String(error)
            });
        }
    };
    HeartbeatHandler.prototype.handleHeartbeatResponse = function (message) {
        var now = Date.now();
        var latency = message.clientTimestamp ? (now - message.clientTimestamp) : -1;
        this.logger.debug('Heartbeat acknowledged', { latency: latency });
        // Clear timeout
        if (this.timeoutId !== null) {
            window.clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }
        // Check device ID validity
        if (!message.deviceIdValid) {
            this.logger.warn("Device ID invalidated in heartbeat. Reason: ".concat(message.reason));
            this.events.emit('deviceIdInvalidated', {
                deviceId: DeviceIdManager.getInstance().getDeviceId(),
                reason: message.reason
            });
            return;
        }
        // Update connection state
        var quality = this.calculateConnectionQuality(latency);
        this.stateManager.updateConnectionState({
            lastHeartbeatTime: now,
            heartbeatLatency: latency >= 0 ? latency : null,
            quality: quality,
            simulatorStatus: message.simulatorStatus
        });
        // Emit response event
        this.events.emit('response', message);
    };
    HeartbeatHandler.prototype.calculateConnectionQuality = function (latency) {
        if (latency < 0)
            return 'UNKNOWN';
        if (latency <= 250)
            return 'GOOD';
        if (latency <= 750)
            return 'DEGRADED';
        return 'POOR';
    };
    HeartbeatHandler.prototype.handleTimeout = function () {
        this.logger.error("Heartbeat timeout after ".concat(this.options.timeout, "ms"));
        this.timeoutId = null;
        this.events.emit('timeout', undefined);
    };
    HeartbeatHandler.prototype.dispose = function () {
        this.stop();
        this.events.clear();
    };
    return HeartbeatHandler;
}());
export { HeartbeatHandler };
