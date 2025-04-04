// src/utils/event-emitter.ts
export class EventEmitter implements Disposable {
  private events: Map<string, Set<Function>> = new Map();
  private subscriptions: Map<object, Map<string, Function>> = new Map();

  /**
   * Subscribe to an event
   */
  public on(event: string, handler: Function): void {
    if (!this.events.has(event)) {
      this.events.set(event, new Set());
    }
    this.events.get(event)?.add(handler);
  }

  /**
   * Subscribe to an event with subscriber tracking for easier cleanup
   */
  public subscribe(subscriber: object, event: string, handler: Function): void {
    // Add to normal events
    this.on(event, handler);
    
    // Track in subscriptions for this subscriber
    if (!this.subscriptions.has(subscriber)) {
      this.subscriptions.set(subscriber, new Map());
    }
    this.subscriptions.get(subscriber)?.set(event, handler);
  }

  /**
   * Unsubscribe from an event
   */
  public off(event: string, handler: Function): void {
    const handlers = this.events.get(event);
    if (handlers) {
      handlers.delete(handler);
      if (handlers.size === 0) {
        this.events.delete(event);
      }
    }
  }

  /**
   * Unsubscribe all handlers for a specific event
   */
  public offAll(event: string): void {
    this.events.delete(event);
    
    // Also clean up from subscriptions tracking
    for (const [subscriber, events] of this.subscriptions.entries()) {
      if (events.has(event)) {
        events.delete(event);
        if (events.size === 0) {
          this.subscriptions.delete(subscriber);
        }
      }
    }
  }

  /**
   * Unsubscribe all handlers for a specific subscriber
   */
  public unsubscribe(subscriber: object): void {
    const events = this.subscriptions.get(subscriber);
    if (!events) return;
    
    // Remove each handler from the events map
    for (const [event, handler] of events.entries()) {
      this.off(event, handler);
    }
    
    // Clean up subscription tracking
    this.subscriptions.delete(subscriber);
  }

  /**
   * Subscribe to an event once
   */
  public once(event: string, handler: Function): void {
    const onceHandler = (...args: any[]) => {
      this.off(event, onceHandler);
      handler(...args);
    };
    this.on(event, onceHandler);
  }

  /**
   * Emit an event
   */
  public emit(event: string, ...args: any[]): void {
    const handlers = this.events.get(event);
    if (handlers) {
      // Create a copy of handlers to avoid issues if handlers are removed during emission
      [...handlers].forEach(handler => {
        try {
          handler(...args);
        } catch (error) {
          console.error(`Error in event handler for "${event}":`, error);
        }
      });
    }
  }

  /**
   * Check if event has listeners
   */
  public hasListeners(event: string): boolean {
    const handlers = this.events.get(event);
    return !!handlers && handlers.size > 0;
  }

  /**
   * Remove all event listeners
   */
  public removeAllListeners(): void {
    this.events.clear();
    this.subscriptions.clear();
  }

  /**
   * Dispose of all resources
   */
  public dispose(): void {
    this.removeAllListeners();
  }
}