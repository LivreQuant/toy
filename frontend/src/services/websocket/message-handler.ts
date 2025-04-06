// src/services/websocket/message-handler.ts
import { EventEmitter } from '../../utils/event-emitter';
import { HeartbeatData } from './types';
import { Logger } from '../../utils/logger';

export class WebSocketMessageHandler {
    private eventEmitter: EventEmitter;
    private logger: Logger;
    private pendingResponses: Map<string, { resolve: Function, reject: Function, timeoutId: number }> = new Map();
    private messageListeners: Map<string, Function[]> = new Map();

    constructor(eventEmitter: EventEmitter, logger: Logger) {
        this.eventEmitter = eventEmitter;
        this.logger = logger.createChild('MessageHandler');
    }

    public on(event: string, listener: Function): void {
        if (!this.messageListeners.has(event)) {
            this.messageListeners.set(event, []);
        }
        this.messageListeners.get(event)?.push(listener);
        this.logger.debug(`Listener added for event: ${event}`);
    }

    public off(event: string, listener: Function): void {
        const listeners = this.messageListeners.get(event);
        if (listeners) {
            const initialLength = listeners.length;
            const updatedListeners = listeners.filter(l => l !== listener);
            if (updatedListeners.length < initialLength) {
                 this.messageListeners.set(event, updatedListeners);
                 this.logger.debug(`Listener removed for event: ${event}`);
            }
             if (updatedListeners.length === 0) {
                 this.messageListeners.delete(event);
                 this.logger.debug(`No listeners remaining for event: ${event}, removing entry.`);
            }
        }
    }

    public handleMessage(event: MessageEvent): void {
        this.logger.debug('Received raw message from WebSocket');
        try {
            const message = JSON.parse(event.data);
            this.logger.debug(`Parsed message type: ${message?.type}`);

            // Trigger general message listeners first
            const generalListeners = this.messageListeners.get('message') || [];
            generalListeners.forEach(listener => {
                try {
                    listener(message);
                } catch (listenerError) {
                    this.logger.error('Error in general message listener', { listenerError });
                }
            });

            // Handle specific message types
            switch (message.type) {
                case 'heartbeat':
                    this.handleHeartbeat(message);
                    break;
                case 'session_invalidated':
                    this.handleSessionInvalidated(message);
                    break;
                case 'session_ready_response':
                    this.logger.debug('Handling session_ready_response');
                    this.eventEmitter.emit('session_ready_response', message);
                    break;
                case 'response':
                    this.handleResponse(message);
                    break;
                case 'order_update':
                    this.logger.debug('Emitting order_update event');
                    this.eventEmitter.emit('order_update', message.data);
                    break;
                // ADD EXCHANGE DATA HANDLER
                case 'exchange_data':
                    this.logger.debug('Handling exchange_data message');
                    this.eventEmitter.emit('exchange_data', message.data);
                    break;
                // ADD PORTFOLIO DATA HANDLER
                case 'portfolio_data':
                    this.logger.debug('Handling portfolio_data message');
                    this.eventEmitter.emit('portfolio_data', message.data);
                    break;
                // ADD RISK DATA HANDLER
                case 'risk_data':
                    this.logger.debug('Handling risk_data message');
                    this.eventEmitter.emit('risk_data', message.data);
                    break;
                default:
                    this.logger.warn(`Unhandled message type: ${message.type}. Emitting as generic 'message'.`);
                    // Emit specific event based on type if listeners exist
                    if (this.messageListeners.has(message.type)) {
                        this.eventEmitter.emit(message.type, message.data || message);
                    } else {
                        // Fallback to emitting as a generic 'unknown_message' or handle as needed
                        this.eventEmitter.emit('unknown_message', message);
                    }
            }
        } catch (error: any) {
            this.logger.error('Failed to parse or handle WebSocket message', { error: error.message, rawData: event.data });
            this.eventEmitter.emit('message_error', {
                error,
                rawData: event.data
            });
        }
    }

    private handleHeartbeat(message: HeartbeatData): void {
        this.logger.debug('Handling heartbeat message');
        this.eventEmitter.emit('heartbeat', {
            timestamp: message.timestamp,
            simulatorStatus: message.simulatorStatus,
            deviceId: message.deviceId
        });
    }

    private handleSessionInvalidated(message: { reason: string }): void {
        this.logger.warn(`Handling session_invalidated message. Reason: ${message.reason}`);
        this.eventEmitter.emit('session_invalidated', {
            reason: message.reason
        });
    }

    private handleResponse(message: any): void {
        const { requestId, error } = message;
        if (!requestId) {
             this.logger.warn('Received response message without requestId', { message });
             return;
        }

        const pending = this.pendingResponses.get(requestId);
        if (pending) {
            this.logger.debug(`Handling response for requestId: ${requestId}`);
            clearTimeout(pending.timeoutId);

            if (error) {
                this.logger.error(`Request failed with server error for requestId: ${requestId}`, { error });
                pending.reject(new Error(error.message || 'Request failed'));
            } else {
                pending.resolve(message);
            }
            this.pendingResponses.delete(requestId);
        } else {
             this.logger.warn(`Received response for unknown or timed out requestId: ${requestId}`);
        }
    }

    public createRequestWithResponse(message: any, timeoutMs = 5000): Promise<any> {
        return new Promise((resolve, reject) => {
            const requestId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
            const messageWithId = { ...message, requestId };

            const timeoutId = window.setTimeout(() => {
                if (this.pendingResponses.has(requestId)) {
                    this.logger.warn(`Request timed out for requestId: ${requestId} (Type: ${message.type})`);
                    this.pendingResponses.delete(requestId);
                    reject(new Error(`Request timeout for type ${message.type} (ID: ${requestId})`));
                }
            }, timeoutMs);

            this.pendingResponses.set(requestId, { resolve, reject, timeoutId });

            this.logger.debug(`Request pending with requestId: ${requestId} (Type: ${message.type})`);
            resolve(messageWithId);
        });
    }

    public clearPendingRequests(reason: string = 'cleanup'): void {
        this.logger.warn(`Clearing all pending requests. Reason: ${reason}`);
        this.pendingResponses.forEach((pending, requestId) => {
            clearTimeout(pending.timeoutId);
            pending.reject(new Error(`Request cancelled due to ${reason} (ID: ${requestId})`));
        });
        this.pendingResponses.clear();
    }

    public removeAllListeners(): void {
        this.messageListeners.clear();
        this.logger.warn('All message listeners removed.');
    }
}