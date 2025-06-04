// src/utils/events.ts
import { getLogger } from '../../../../apps/legacy/src/boot/logging';
export class EventEmitter {
    constructor() {
        this.handlers = new Map();
        this.logger = getLogger('EventEmitter');
        this.events = {};
    }
    /**
     * Register an event handler
     */
    on(event, handler) {
        // Get or create the handler set for this event
        if (!this.handlers.has(event)) {
            this.handlers.set(event, new Set());
        }
        const handlers = this.handlers.get(event);
        handlers.add(handler);
        return {
            unsubscribe: () => {
                handlers.delete(handler);
                if (handlers.size === 0) {
                    this.handlers.delete(event);
                }
            }
        };
    }
    /**
     * Register a one-time event handler
     */
    once(event, handler) {
        const subscription = this.on(event, (data) => {
            subscription.unsubscribe();
            handler(data);
        });
        return subscription;
    }
    /**
     * Emit an event with data
     */
    emit(event, data) {
        if (!this.handlers.has(event)) {
            return;
        }
        const handlers = this.handlers.get(event);
        handlers.forEach(handler => {
            try {
                handler(data);
            }
            catch (error) {
                this.logger.error(`Error in event handler for "${String(event)}"`, {
                    error: error instanceof Error ? error.message : String(error),
                    handlerName: handler.name || '(anonymous)'
                });
            }
        });
    }
    /**
     * Remove all event handlers
     */
    clear() {
        this.handlers.clear();
    }
    /**
     * Get the number of handlers for an event
     */
    handlerCount(event) {
        return this.handlers.has(event) ? this.handlers.get(event).size : 0;
    }
}
