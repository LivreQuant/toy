// src/handlers/heartbeat-handler.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { EventEmitter } from '@trading-app/utils';
export class HeartbeatHandler {
    constructor(client, stateManager, options) {
        this.client = client;
        this.stateManager = stateManager;
        this.options = options;
        this.logger = getLogger('HeartbeatHandler');
        this.intervalId = null;
        this.timeoutId = null;
        this.lastTimestamp = 0;
        this.events = new EventEmitter();
        this.logger.info('HeartbeatHandler initialized', { options });
    }
    start() {
        this.logger.info('Starting heartbeat monitoring');
        this.stop(); // Clear any existing timers
        // Set up message listener
        const subscription = this.client.on('message', (message) => {
            if (message.type === 'heartbeat_ack') {
                this.handleHeartbeatResponse(message);
            }
        });
        // Start sending heartbeats
        this.sendHeartbeat();
        this.intervalId = window.setInterval(() => this.sendHeartbeat(), this.options.interval);
    }
    stop() {
        this.logger.info('Stopping heartbeat monitoring');
        if (this.intervalId !== null) {
            window.clearInterval(this.intervalId);
            this.intervalId = null;
        }
        if (this.timeoutId !== null) {
            window.clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }
    }
    on(event, callback) {
        return this.events.on(event, callback);
    }
    sendHeartbeat() {
        if (this.client.getCurrentStatus() !== ConnectionStatus.CONNECTED) {
            this.logger.debug('Skipping heartbeat: client not connected');
            return;
        }
        const timestamp = Date.now();
        this.lastTimestamp = timestamp;
        const message = {
            type: 'heartbeat',
            timestamp,
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
            this.timeoutId = window.setTimeout(() => this.handleTimeout(), this.options.timeout);
        }
        catch (error) {
            this.logger.error('Failed to send heartbeat', {
                error: error instanceof Error ? error.message : String(error)
            });
        }
    }
    handleHeartbeatResponse(message) {
        const now = Date.now();
        const latency = message.clientTimestamp ? (now - message.clientTimestamp) : -1;
        this.logger.debug('Heartbeat acknowledged', { latency });
        // Clear timeout
        if (this.timeoutId !== null) {
            window.clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }
        // Check device ID validity
        if (!message.deviceIdValid) {
            this.logger.warn(`Device ID invalidated in heartbeat. Reason: ${message.reason}`);
            this.events.emit('deviceIdInvalidated', {
                deviceId: DeviceIdManager.getInstance().getDeviceId(),
                reason: message.reason
            });
            return;
        }
        // Update connection state
        const quality = this.calculateConnectionQuality(latency);
        this.stateManager.updateConnectionState({
            lastHeartbeatTime: now,
            heartbeatLatency: latency >= 0 ? latency : null,
            quality,
            simulatorStatus: message.simulatorStatus
        });
        // Emit response event
        this.events.emit('response', message);
    }
    calculateConnectionQuality(latency) {
        if (latency < 0)
            return 'UNKNOWN';
        if (latency <= 250)
            return 'GOOD';
        if (latency <= 750)
            return 'DEGRADED';
        return 'POOR';
    }
    handleTimeout() {
        this.logger.error(`Heartbeat timeout after ${this.options.timeout}ms`);
        this.timeoutId = null;
        this.events.emit('timeout', undefined);
    }
    dispose() {
        this.stop();
        this.events.clear();
    }
}
