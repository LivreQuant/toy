// src/utils/events.ts
import { getLogger } from '../boot/logging';

export class EventEmitter<T extends Record<string, any>> {
  public readonly events: T;
  private handlers: Map<keyof T, Set<(data: any) => void>> = new Map();
  private logger = getLogger('EventEmitter');

  constructor() {
    // This is just to make TypeScript happy with the generic type
    this.events = {} as T;
  }

  /**
   * Register an event handler
   */
  public on<K extends keyof T>(
    event: K,
    handler: (data: T[K]) => void
  ): { unsubscribe: () => void } {
    // Get or create the handler set for this event
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set());
    }

    const handlers = this.handlers.get(event)!;
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
  public once<K extends keyof T>(
    event: K,
    handler: (data: T[K]) => void
  ): { unsubscribe: () => void } {
    const subscription = this.on(event, (data) => {
      subscription.unsubscribe();
      handler(data);
    });

    return subscription;
  }

  /**
   * Emit an event with data
   */
  public emit<K extends keyof T>(event: K, data: T[K]): void {
    if (!this.handlers.has(event)) {
      return;
    }

    const handlers = this.handlers.get(event)!;
    handlers.forEach(handler => {
      try {
        handler(data);
      } catch (error: any) {
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
  public clear(): void {
    this.handlers.clear();
  }

  /**
   * Get the number of handlers for an event
   */
  public handlerCount(event: keyof T): number {
    return this.handlers.has(event) ? this.handlers.get(event)!.size : 0;
  }
}