// src/services/websocket/connection-strategy.ts
import { config } from '../../config';
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
// Import the *class* DeviceIdManager, not just static methods
import { DeviceIdManager } from '../../utils/device-id-manager';
import { ConnectionStrategyDependencies, WebSocketOptions } from './types'; // Assuming DeviceIdManager added here
import { Logger } from '../../utils/logger'; // Import Logger


export class ConnectionStrategy {
    private tokenManager: TokenManager;
    private deviceIdManager: DeviceIdManager; // Store the instance
    private eventEmitter: EventEmitter;
    private logger: Logger; // Store the instance
    private options: WebSocketOptions;
    private ws: WebSocket | null = null;

    constructor({
        tokenManager,
        deviceIdManager, // Receive instance
        eventEmitter,
        logger, // Receive instance
        options = {}
    }: ConnectionStrategyDependencies) {
        this.tokenManager = tokenManager;
        this.deviceIdManager = deviceIdManager; // Assign instance
        this.eventEmitter = eventEmitter;
        this.logger = logger.createChild('ConnectionStrategy'); // Create child logger
        this.options = {
            heartbeatInterval: 15000,
            heartbeatTimeout: 5000,
            reconnectMaxAttempts: 5,
            ...options
        };
        this.logger.info('ConnectionStrategy instance created.');
    }

    public async connect(): Promise<WebSocket> {
        this.logger.info('Attempting to connect WebSocket...');
        const token = await this.tokenManager.getAccessToken();
        if (!token) {
            this.logger.error('WebSocket connect failed: No authentication token available.');
            throw new Error('No authentication token available');
        }

        // Use the injected DeviceIdManager instance
        const deviceId = this.deviceIdManager.getDeviceId();
        this.logger.info(`Using Device ID: ${deviceId}`); // Log the obtained ID

        const params = new URLSearchParams({
            token: token, // Be cautious logging tokens, even in dev
            deviceId,
            userAgent: navigator.userAgent // Consider if this is truly needed/useful
        });

        const wsUrl = `${config.wsBaseUrl}?${params.toString()}`;
        this.logger.info('Connecting to WebSocket URL:', { url: config.wsBaseUrl }); // Log base URL only

        // Close existing socket if attempting to reconnect
        if (this.ws) {
            this.logger.warn('Closing existing WebSocket before creating a new one.');
            this.disconnect(); // Use the disconnect method to clean up listeners
        }

        this.ws = new WebSocket(wsUrl);
        this.logger.info('WebSocket instance created.');

        return new Promise((resolve, reject) => {
            if (!this.ws) {
                 // Should not happen if constructor succeeded, but defensive check
                this.logger.error('WebSocket instance is null after creation.');
                reject(new Error('Failed to create WebSocket instance'));
                return;
            }

            // Clear previous listeners before attaching new ones
            this.ws.onopen = null;
            this.ws.onclose = null;
            this.ws.onerror = null;
            this.ws.onmessage = null; // Ensure message listener is handled elsewhere (WebSocketManager)


            this.ws.onopen = () => {
                this.logger.info('WebSocket connection opened successfully.');
                // Emit internal 'connected' event - WebSocketManager listens for this
                this.eventEmitter.emit('ws_connected_internal'); // Use a more specific internal event name
                resolve(this.ws!); // Resolve with the WebSocket instance
            };

            this.ws.onclose = (event: CloseEvent) => {
                this.logger.warn(`WebSocket connection closed. Code: ${event.code}, Reason: "${event.reason}", Clean: ${event.wasClean}`);
                // Emit internal 'disconnected' event with details
                this.eventEmitter.emit('ws_disconnected_internal', {
                    code: event.code,
                    reason: event.reason,
                    wasClean: event.wasClean
                });
                // Don't reject the promise here; disconnection is handled by WebSocketManager's listener
                this.ws = null; // Clear the instance on close
            };

            this.ws.onerror = (event: Event) => { // event is usually of type Event
                this.logger.error('WebSocket error event occurred.', { event });
                // Emit internal 'error' event - WebSocketManager listens for this
                // Pass a structured error object
                this.eventEmitter.emit('ws_error_internal', {
                    message: 'WebSocket connection error event',
                    originalEvent: event
                 });
                // Reject the promise *only if the connection never opened*
                if (this.ws?.readyState !== WebSocket.OPEN) {
                     reject(new Error('WebSocket connection error during setup'));
                }
                // Don't reject if the error occurs after connection was established
            };
        });
    }

    public disconnect(): void {
        if (this.ws) {
            this.logger.warn('Disconnecting WebSocket connection.');
            // Remove listeners before closing to prevent events firing after explicit disconnect
            this.ws.onopen = null;
            this.ws.onmessage = null; // Message handling is likely in WebSocketManager
            this.ws.onerror = null;
            this.ws.onclose = null; // Prevent the onclose handler from triggering reconnect logic if manual

            // Close only if not already closing or closed
            if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
                this.ws.close(1000, 'Client disconnected'); // Use standard code 1000 for normal closure
            }
            this.ws = null; // Clear the reference
        } else {
            this.logger.info('Disconnect called but no active WebSocket connection found.');
        }
    }

    public getWebSocket(): WebSocket | null {
        return this.ws;
    }
}

