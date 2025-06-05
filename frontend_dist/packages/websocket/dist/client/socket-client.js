// src/client/socket-client.ts
import { BehaviorSubject } from 'rxjs';
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';
import { ConnectionStatus } from '@trading-app/state';
import { EventEmitter } from '@trading-app/utils';
export class SocketClient {
    constructor(tokenManager, configService, options) {
        this.tokenManager = tokenManager;
        this.configService = configService;
        this.logger = getLogger('SocketClient');
        this.socket = null;
        this.status$ = new BehaviorSubject(ConnectionStatus.DISCONNECTED);
        this.events = new EventEmitter();
        // Handle incoming messages
        this.handleMessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.events.emit('message', message);
            }
            catch (error) {
                this.logger.error('Error parsing WebSocket message', {
                    error: error instanceof Error ? error.message : String(error),
                    data: typeof event.data === 'string' ? event.data.substring(0, 100) : 'non-string data'
                });
                this.events.emit('error', error instanceof Error ? error : new Error(String(error)));
            }
        };
        // Handle connection close
        this.handleClose = (event) => {
            this.logger.info(`WebSocket connection closed. Code: ${event.code}, Reason: ${event.reason}, Clean: ${event.wasClean}`);
            this.cleanup();
            this.status$.next(ConnectionStatus.DISCONNECTED);
            this.events.emit('close', {
                code: event.code,
                reason: event.reason,
                wasClean: event.wasClean
            });
        };
        this.options = {
            autoReconnect: false,
            connectTimeout: 10000,
            secureConnection: false,
            ...options
        };
    }
    // Get the connection status observable
    getStatus() {
        return this.status$.asObservable();
    }
    // Get the current connection status
    getCurrentStatus() {
        return this.status$.getValue();
    }
    // Connect to the WebSocket server
    async connect() {
        if (this.socket) {
            this.logger.warn('Connect called with existing socket, cleaning up previous instance');
            this.cleanup();
        }
        if (!this.tokenManager.isAuthenticated()) {
            this.logger.error('Cannot connect: Not authenticated');
            this.status$.next(ConnectionStatus.DISCONNECTED);
            return false;
        }
        const currentStatus = this.status$.getValue();
        if (currentStatus === ConnectionStatus.CONNECTING || currentStatus === ConnectionStatus.CONNECTED) {
            this.logger.warn(`Connect call ignored: WebSocket status is already ${currentStatus}`);
            return currentStatus === ConnectionStatus.CONNECTED;
        }
        try {
            this.logger.info('Initiating WebSocket connection...');
            this.status$.next(ConnectionStatus.CONNECTING);
            const token = await this.tokenManager.getAccessToken();
            if (!token) {
                throw new Error('Failed to get authentication token for WebSocket');
            }
            const csrfToken = await this.tokenManager.getCsrfToken();
            const deviceId = DeviceIdManager.getInstance().getDeviceId();
            const params = new URLSearchParams({
                token,
                deviceId,
                csrfToken
            });
            const wsUrl = `${this.configService.getWebSocketUrl()}?${params.toString()}`;
            this.socket = new WebSocket(wsUrl);
            return new Promise((resolve) => {
                const timeoutId = setTimeout(() => {
                    this.logger.error('WebSocket connection attempt timed out');
                    if (this.status$.getValue() === ConnectionStatus.CONNECTING) {
                        this.cleanup();
                        this.status$.next(ConnectionStatus.DISCONNECTED);
                        resolve(false);
                    }
                }, this.options.connectTimeout);
                this.socket.addEventListener('open', () => {
                    clearTimeout(timeoutId);
                    this.logger.info('WebSocket connection established');
                    this.status$.next(ConnectionStatus.CONNECTED);
                    this.events.emit('open', undefined);
                    resolve(true);
                });
                this.socket.addEventListener('error', (event) => {
                    this.logger.error('WebSocket connection error', { event });
                    this.events.emit('error', new Error('WebSocket connection error'));
                });
                this.socket.addEventListener('close', (event) => {
                    clearTimeout(timeoutId);
                    this.handleClose(event);
                    if (this.status$.getValue() === ConnectionStatus.CONNECTING) {
                        resolve(false);
                    }
                });
                this.socket.addEventListener('message', this.handleMessage);
            });
        }
        catch (error) {
            this.logger.error('Error initiating WebSocket connection', {
                error: error instanceof Error ? error.message : String(error)
            });
            this.status$.next(ConnectionStatus.DISCONNECTED);
            return false;
        }
    }
    // Disconnect from the WebSocket server
    disconnect(reason = 'manual') {
        this.logger.info(`Disconnecting WebSocket. Reason: ${reason}`);
        if (this.socket) {
            if (this.socket.readyState === WebSocket.OPEN) {
                this.socket.close(1000, reason);
            }
            else {
                this.cleanup();
            }
        }
        this.status$.next(ConnectionStatus.DISCONNECTED);
    }
    // Send a message to the WebSocket server
    send(data) {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
            this.logger.error('Cannot send message: WebSocket not connected');
            return false;
        }
        try {
            this.socket.send(typeof data === 'string' ? data : JSON.stringify(data));
            return true;
        }
        catch (error) {
            this.logger.error('Error sending WebSocket message', {
                error: error instanceof Error ? error.message : String(error)
            });
            return false;
        }
    }
    // Listen for events
    on(event, callback) {
        return this.events.on(event, callback);
    }
    // Clean up WebSocket resources
    cleanup() {
        if (this.socket) {
            this.socket.removeEventListener('message', this.handleMessage);
            this.socket.removeEventListener('close', this.handleClose);
            this.socket.onopen = null;
            this.socket.onclose = null;
            this.socket.onerror = null;
            if (this.socket.readyState === WebSocket.OPEN ||
                this.socket.readyState === WebSocket.CONNECTING) {
                try {
                    this.socket.close(1000, 'Client cleanup');
                }
                catch (e) {
                    this.logger.warn('Error closing WebSocket during cleanup');
                }
            }
            this.socket = null;
        }
    }
    // Implement Disposable interface
    dispose() {
        this.disconnect('disposed');
        this.events.clear();
        this.status$.complete();
    }
}
