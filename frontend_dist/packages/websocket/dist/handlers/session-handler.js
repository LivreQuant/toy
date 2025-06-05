// src/handlers/session-handler.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
export class SessionHandler {
    constructor(client) {
        this.client = client;
        this.logger = getLogger('SessionHandler');
        this.responseTimeoutMs = 15000;
        this.logger.info('SessionHandler initialized');
    }
    async requestSessionInfo() {
        this.logger.info('Requesting session information');
        const requestId = `session-info-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
        const message = {
            type: 'request_session',
            requestId,
            timestamp: Date.now(),
            deviceId: DeviceIdManager.getInstance().getDeviceId()
        };
        try {
            const response = await this.sendRequest(message, (msg) => msg.type === 'session_info' && msg.requestId === requestId);
            this.logger.info('Session info response received', response);
            return {
                ...response,
                success: true,
                userId: response.userId || 'unknown',
                status: response.status || 'active',
                createdAt: response.createdAt || Date.now(),
                simulatorId: response.simulatorId || null
            };
        }
        catch (error) {
            this.logger.error('Error requesting session info', {
                error: error instanceof Error ? error.message : String(error)
            });
            throw error;
        }
    }
    async stopSession() {
        this.logger.info('Requesting session stop');
        const requestId = `stop-session-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
        const message = {
            type: 'stop_session',
            requestId,
            timestamp: Date.now(),
            deviceId: DeviceIdManager.getInstance().getDeviceId()
        };
        return this.sendRequest(message, (msg) => msg.type === 'session_stopped' && msg.requestId === requestId);
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
