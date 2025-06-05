// src/handlers/simulator-handler.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
export class SimulatorHandler {
    constructor(client) {
        this.client = client;
        this.logger = getLogger('SimulatorHandler');
        this.responseTimeoutMs = 15000;
        this.logger.info('SimulatorHandler initialized');
    }
    async startSimulator() {
        this.logger.info('Requesting simulator start');
        const requestId = `start-simulator-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
        const message = {
            type: 'start_simulator',
            requestId,
            timestamp: Date.now(),
            deviceId: DeviceIdManager.getInstance().getDeviceId()
        };
        return this.sendRequest(message, (msg) => msg.type === 'simulator_started' && msg.requestId === requestId);
    }
    async stopSimulator() {
        this.logger.info('Requesting simulator stop');
        const requestId = `stop-simulator-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
        const message = {
            type: 'stop_simulator',
            requestId,
            timestamp: Date.now(),
            deviceId: DeviceIdManager.getInstance().getDeviceId()
        };
        return this.sendRequest(message, (msg) => msg.type === 'simulator_stopped' && msg.requestId === requestId);
    }
    async sendRequest(message, predicate) {
        return new Promise((resolve, reject) => {
            const timeoutId = window.setTimeout(() => {
                subscription.unsubscribe();
                reject(new Error(`Request timed out after ${this.responseTimeoutMs}ms`));
            }, this.responseTimeoutMs);
            const subscription = this.client.on('message', (msg) => {
                if (predicate(msg)) {
                    window.clearTimeout(timeoutId);
                    subscription.unsubscribe();
                    resolve(msg);
                }
            });
            if (!this.client.send(message)) {
                window.clearTimeout(timeoutId);
                subscription.unsubscribe();
                reject(new Error('Failed to send request: client not connected'));
            }
        });
    }
}
