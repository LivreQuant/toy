// src/utils/event-emitter.ts
import { Disposable } from './disposable'; // Assuming Disposable interface is defined

/**
 * A basic event emitter class implementing the Disposable interface
 * for explicit resource cleanup.
 */
export class EventEmitter implements Disposable {
  // Stores event names and their corresponding Set of handler functions
  private events: Map<string, Set<Function>> = new Map();
  // Tracks subscriptions per subscriber object for easier mass unsubscription
  private subscriptions: Map<object, Map<string, Function>> = new Map();

  /**
   * Subscribe a handler function to an event.
   * @param event - The name of the event.
   * @param handler - The function to call when the event is emitted.
   */
  public on(event: string, handler: Function): void {
    if (!this.events.has(event)) {
      this.events.set(event, new Set());
    }
    this.events.get(event)?.add(handler);
  }

  /**
   * Subscribe a handler function to an event and track it by subscriber object.
   * This allows unsubscribing all handlers for a specific subscriber easily.
   * @param subscriber - The object instance subscribing to the event.
   * @param event - The name of the event.
   * @param handler - The function to call when the event is emitted.
   */
  public subscribe(subscriber: object, event: string, handler: Function): void {
    // Add to the main event registry
    this.on(event, handler);

    // Track the subscription under the subscriber object
    if (!this.subscriptions.has(subscriber)) {
      this.subscriptions.set(subscriber, new Map());
    }
    // Store the event and handler associated with the subscriber
    this.subscriptions.get(subscriber)?.set(event, handler);
  }

  /**
   * Unsubscribe a specific handler function from an event.
   * @param event - The name of the event.
   * @param handler - The specific handler function to remove.
   */
  public off(event: string, handler: Function): void {
    const handlers = this.events.get(event);
    if (handlers) {
      handlers.delete(handler);
      // If no handlers remain for this event, remove the event entry
      if (handlers.size === 0) {
        this.events.delete(event);
      }
    }
  }

  /**
   * Unsubscribe all handler functions for a specific event.
   * @param event - The name of the event to remove all listeners for.
   */
  public offAll(event: string): void {
    // Remove from the main event registry
    this.events.delete(event);

    // Remove this event from all subscriber tracking maps
    for (const [subscriber, eventsMap] of this.subscriptions.entries()) {
      if (eventsMap.has(event)) {
        eventsMap.delete(event);
        // If the subscriber has no more tracked events, remove the subscriber entry
        if (eventsMap.size === 0) {
          this.subscriptions.delete(subscriber);
        }
      }
    }
  }

  /**
   * Unsubscribe all handlers associated with a specific subscriber object.
   * @param subscriber - The object whose handlers should be removed.
   */
  public unsubscribe(subscriber: object): void {
    const subscriberEvents = this.subscriptions.get(subscriber);
    if (!subscriberEvents) return; // No tracked subscriptions for this subscriber

    // Iterate through the tracked events for this subscriber and remove them
    for (const [event, handler] of subscriberEvents.entries()) {
      this.off(event, handler); // Use 'off' to remove from the main registry
    }

    // Remove the subscriber entry from the tracking map
    this.subscriptions.delete(subscriber);
  }

  /**
   * Subscribe a handler function to an event for only one emission.
   * The handler is automatically unsubscribed after being called once.
   * @param event - The name of the event.
   * @param handler - The function to call once when the event is emitted.
   */
  public once(event: string, handler: Function): void {
    // Create a wrapper function that unsubscribes itself before calling the original handler
    const onceHandler = (...args: any[]) => {
      this.off(event, onceHandler); // Unsubscribe the wrapper
      handler(...args); // Call the original handler
    };
    // Subscribe the wrapper function
    this.on(event, onceHandler);
  }

  /**
   * Emit an event, calling all subscribed handler functions.
   * @param event - The name of the event to emit.
   * @param args - Arguments to pass to the handler functions.
   */
  public emit(event: string, ...args: any[]): void {
    const handlers = this.events.get(event);
    if (handlers) {
      // Create a copy of the handlers Set using the spread operator.
      // This prevents issues if a handler unsubscribes itself or another handler
      // during the emission loop, which would modify the Set while iterating.
      [...handlers].forEach(handler => {
        try {
          // Call the handler with the provided arguments
          handler(...args);
        } catch (error) {
          // Log errors that occur within event handlers to prevent them
          // from stopping the emission process for other handlers.
          console.error(`Error in event handler for "${event}":`, error);
        }
      });
    }
  }

  /**
   * Checks if there are any listeners subscribed to a specific event.
   * @param event - The name of the event.
   * @returns True if there is at least one listener, false otherwise.
   */
  public hasListeners(event: string): boolean {
    const handlers = this.events.get(event);
    return !!handlers && handlers.size > 0;
  }

  /**
   * Removes all event listeners for all events. Clears all tracking.
   */
  public removeAllListeners(): void {
    this.events.clear();
    this.subscriptions.clear();
    console.warn("EventEmitter: All listeners removed."); // Log this potentially significant action
  }

  /**
   * Cleans up all resources used by the EventEmitter (removes all listeners).
   * Implements the `dispose` method from the `Disposable` interface.
   */
  public dispose(): void {
    this.removeAllListeners();
  }

  /**
   * Implements the `[Symbol.dispose]` method for explicit resource management.
   * This allows using the `using` keyword in environments that support it.
   * It simply calls the existing `dispose` method.
   */
  [Symbol.dispose](): void {
    this.dispose();
  }
}
