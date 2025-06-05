// src/services/heartbeat.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { EventEmitter } from '@trading-app/utils';
export class Heartbeat {
    constructor(client, stateManager, options) {
        this.client = client;
        this.stateManager = stateManager;
        this.logger = getLogger('Heartbeat');
        this.heartbeatIntervalId = null;
        this.heartbeatTimeoutId = null;
        this.isStarted = false;
        this.isDisposed = false;
        this.lastHeartbeatTimestamp = 0;
        this.events = new EventEmitter();
        const defaultOptions = {
            interval: 15000,
            timeout: 5000
        };
        this.options = { ...defaultOptions, ...(options || {}) };
        this.logger.info('Heartbeat initialized', { options: this.options });
        this.client.on('message', (message) => {
            if (message.type === 'heartbeat_ack') {
                this.handleHeartbeatResponse(message);
            }
        });
    }
    isActive() {
        return this.isStarted && !this.isDisposed;
    }
    start() {
        if (this.isStarted || this.isDisposed) {
            this.logger.debug('Heartbeat start ignored: Already started or disposed');
            return;
        }
        this.logger.info('Starting heartbeats...');
        this.isStarted = true;
        this.sendHeartbeat();
        this.scheduleNextHeartbeat();
    }
    stop() {
        if (!this.isStarted || this.isDisposed) {
            this.logger.debug('Heartbeat stop ignored: Not running or disposed');
            return;
        }
        this.logger.info('Stopping heartbeats...');
        this.isStarted = false;
        this.clearHeartbeatInterval();
        this.clearHeartbeatTimeout();
    }
    on(event, callback) {
        return this.events.on(event, callback);
    }
    scheduleNextHeartbeat() {
        this.clearHeartbeatInterval();
        this.heartbeatIntervalId = window.setInterval(() => {
            this.sendHeartbeat();
        }, this.options.interval);
    }
    sendHeartbeat() {
        if (!this.isStarted || this.isDisposed)
            return;
        if (this.client.getCurrentStatus() !== ConnectionStatus.CONNECTED) {
            this.logger.debug('Skipping heartbeat: WebSocket not connected');
            return;
        }
        this.logger.debug('Sending heartbeat');
        const heartbeatMsg = {
            type: 'heartbeat',
            timestamp: Date.now(),
            deviceId: DeviceIdManager.getInstance().getDeviceId()
        };
        try {
            this.client.send(heartbeatMsg);
            this.clearHeartbeatTimeout();
            this.heartbeatTimeoutId = window.setTimeout(() => {
                this.handleHeartbeatTimeout();
            }, this.options.timeout);
        }
        catch (error) {
            this.logger.error('Failed to send heartbeat', {
                error: error instanceof Error ? error.message : String(error)
            });
        }
    }
    handleHeartbeatResponse(message) {
        this.lastHeartbeatTimestamp = Date.now();
        this.logger.debug('Heartbeat Response Analysis', {
            deviceIdValid: message.deviceIdValid,
            simulatorStatus: message.simulatorStatus,
            clientTimestamp: message.clientTimestamp,
            serverTimestamp: Date.now(),
            latency: message.clientTimestamp ? (Date.now() - message.clientTimestamp) : -1
        });
        this.clearHeartbeatTimeout();
        const latency = message.clientTimestamp ? (Date.now() - message.clientTimestamp) : -1;
        // Update state through injected state manager
        if (latency >= 0) {
            const quality = this.calculateConnectionQuality(latency);
            this.stateManager.updateConnectionState({
                lastHeartbeatTime: Date.now(),
                heartbeatLatency: latency,
                quality,
                simulatorStatus: message.simulatorStatus
            });
        }
        this.events.emit('response', {
            latency,
            deviceIdValid: message.deviceIdValid,
            simulatorStatus: message.simulatorStatus
        });
    }
    calculateConnectionQuality(latency) {
        if (latency <= 250)
            return 'GOOD';
        if (latency <= 750)
            return 'DEGRADED';
        return 'POOR';
    }
    handleHeartbeatTimeout() {
        this.logger.error('Heartbeat timeout detected');
        this.events.emit('timeout', undefined);
    }
    clearHeartbeatInterval() {
        if (this.heartbeatIntervalId !== null) {
            window.clearInterval(this.heartbeatIntervalId);
            this.heartbeatIntervalId = null;
        }
    }
    clearHeartbeatTimeout() {
        if (this.heartbeatTimeoutId !== null) {
            window.clearTimeout(this.heartbeatTimeoutId);
            this.heartbeatTimeoutId = null;
        }
    }
    dispose() {
        if (this.isDisposed)
            return;
        this.isDisposed = true;
        this.stop();
        this.events.clear();
        this.logger.info('Heartbeat disposed');
    }
}
