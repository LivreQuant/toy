// src/services/websocket/message-handler.ts
import { EventEmitter } from '../../utils/event-emitter';
import { HeartbeatData } from './types';
import { Logger } from '../../utils/logger'; // Assuming logger is needed

export class WebSocketMessageHandler {
    private eventEmitter: EventEmitter;
    private logger: Logger; // Add logger instance
    private pendingResponses: Map<string, { resolve: Function, reject: Function, timeoutId: number }> = new Map(); // Store reject and timeoutId
    private messageListeners: Map<string, Function[]> = new Map();

    constructor(eventEmitter: EventEmitter, logger: Logger) {
        this.eventEmitter = eventEmitter;
        this.logger = logger.createChild('MessageHandler'); // Create child logger
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
                // REMOVED 'claim_master' case - relying on 'session_invalidated' from backend
                // case 'claim_master':
                //     this.handleClaimMaster(message); // Method removed below
                //     break;
                case 'session_invalidated':
                    // This message now handles both general invalidation and superseded tabs (if backend sends it)
                    this.handleSessionInvalidated(message);
                    break;
                case 'session_ready_response': // Example specific message type
                    this.logger.debug('Handling session_ready_response');
                    this.eventEmitter.emit('session_ready_response', message); // Emit specific event
                    break;
                case 'response':
                    this.handleResponse(message);
                    break;
                // Handle other specific message types by emitting events
                case 'order_update': // Example
                    this.logger.debug('Emitting order_update event');
                    this.eventEmitter.emit('order_update', message.data);
                    break;
                case 'exchange_data': // Example
                     this.logger.debug('Emitting exchange_data event');
                     this.eventEmitter.emit('exchange_data', message.data);
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
        // Emit specific heartbeat event for WebSocketManager
        this.eventEmitter.emit('heartbeat', {
            timestamp: message.timestamp,
            isMaster: message.isMaster, // Keep isMaster if backend still sends it, though claim_master is removed
            simulatorStatus: message.simulatorStatus,
            deviceId: message.deviceId
        });
    }

    // REMOVED handleClaimMaster method entirely
    // private handleClaimMaster(message: { deviceId: string }): void { ... }

    private handleSessionInvalidated(message: { reason: string }): void {
        this.logger.warn(`Handling session_invalidated message. Reason: ${message.reason}`);
        // Emit specific event for WebSocketManager
        // This event will now trigger logout for any invalidation reason, including being superseded
        this.eventEmitter.emit('session_invalidated', {
            reason: message.reason
        });
    }

    private handleResponse(message: any): void {
        const { requestId, error } = message; // Check for potential error field in response
        if (!requestId) {
             this.logger.warn('Received response message without requestId', { message });
             return;
        }

        const pending = this.pendingResponses.get(requestId);
        if (pending) {
            this.logger.debug(`Handling response for requestId: ${requestId}`);
            clearTimeout(pending.timeoutId); // Clear the timeout

            if (error) {
                this.logger.error(`Request failed with server error for requestId: ${requestId}`, { error });
                pending.reject(new Error(error.message || 'Request failed')); // Reject promise with error
            } else {
                pending.resolve(message); // Resolve promise with the full response
            }
            this.pendingResponses.delete(requestId); // Clean up map entry
        } else {
             this.logger.warn(`Received response for unknown or timed out requestId: ${requestId}`);
        }
    }

    /**
     * Wraps a message payload with a unique requestId and sets up response handling.
     * To be used typically before sending the message via WebSocketManager.send().
     * @param message The message payload to send.
     * @param timeoutMs Timeout duration in milliseconds (default: 5000).
     * @returns A Promise that resolves with the server's response or rejects on timeout/error.
     */
    public createRequestWithResponse(message: any, timeoutMs = 5000): Promise<any> {
        return new Promise((resolve, reject) => {
            const requestId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
            const messageWithId = { ...message, requestId };

            const timeoutId = window.setTimeout(() => {
                // Explicitly clean up and reject on timeout
                if (this.pendingResponses.has(requestId)) {
                    this.logger.warn(`Request timed out for requestId: ${requestId} (Type: ${message.type})`);
                    this.pendingResponses.delete(requestId);
                    reject(new Error(`Request timeout for type ${message.type} (ID: ${requestId})`));
                }
            }, timeoutMs);

            // Store resolve, reject, and timeoutId for later handling
            this.pendingResponses.set(requestId, { resolve, reject, timeoutId });

            this.logger.debug(`Request pending with requestId: ${requestId} (Type: ${message.type})`);
            // IMPORTANT: This method *creates* the request object and promise setup.
            // The actual sending (`wsManager.send(messageWithId)`) must happen separately.
            // Consider returning messageWithId if the caller needs it for sending.
            // For simplicity here, assuming the side effect of adding to pendingResponses is sufficient.
            // Let's return messageWithId to make sending explicit for the caller.
            // --> The caller should then do: wsManager.send(messageWithId);
             // Resolve the promise with the message to be sent
             resolve(messageWithId); // Resolve with the message to be sent by the caller
        });
    }

     /**
     * Cleans up any pending requests, typically called on disconnect or disposal.
     */
    public clearPendingRequests(reason: string = 'cleanup'): void {
        this.logger.warn(`Clearing all pending requests. Reason: ${reason}`);
        this.pendingResponses.forEach((pending, requestId) => {
            clearTimeout(pending.timeoutId);
            pending.reject(new Error(`Request cancelled due to ${reason} (ID: ${requestId})`));
        });
        this.pendingResponses.clear();
    }

     /**
      * Removes all registered listeners.
      */
     public removeAllListeners(): void {
         this.messageListeners.clear();
         this.logger.warn('All message listeners removed.');
     }
}
