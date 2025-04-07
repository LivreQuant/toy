// src/utils/typed-event-emitter.ts
import { Subject, Observable, Subscription } from 'rxjs';
import { filter, map } from 'rxjs/operators';
import { Disposable } from '../../utils/disposable';
import { Logger } from '../../utils/logger';

// Type for event map - define event names and their payload types
export type EventMap = Record<string, any>;

export class TypedEventEmitter<T extends EventMap> implements Disposable {
  private subject = new Subject<{ type: keyof T; payload: any }>();
  private logger: Logger;
  private subscriptions: Subscription[] = [];

  constructor(loggerName: string = 'EventEmitter') {
    this.logger = Logger.getInstance().createChild(loggerName);
  }

  // Emit an event with typed payload
  emit<K extends keyof T>(type: K, payload: T[K]): void {
    this.logger.debug(`Emitting event: ${String(type)}`);
    this.subject.next({ type, payload });
  }

  // Get an observable for a specific event type
  on<K extends keyof T>(type: K): Observable<T[K]> {
    return this.subject.pipe(
      filter(event => event.type === type),
      map(event => event.payload as T[K])
    );
  }

  // Subscribe to an event with a callback
  subscribe<K extends keyof T>(type: K, handler: (payload: T[K]) => void): Subscription {
    const subscription = this.on(type).subscribe(
      payload => {
        try {
          handler(payload);
        } catch (error) {
          this.logger.error(`Error in event handler for "${String(type)}":`, { error });
        }
      }
    );
    
    this.subscriptions.push(subscription);
    return subscription;
  }

  // Subscribe once to an event
  once<K extends keyof T>(type: K, handler: (payload: T[K]) => void): Subscription {
    const subscription = this.on(type).pipe(
      // take(1) // Only take the first emission
    ).subscribe(
      payload => {
        try {
          handler(payload);
        } catch (error) {
          this.logger.error(`Error in once event handler for "${String(type)}":`, { error });
        }
        subscription.unsubscribe();
      }
    );
    
    this.subscriptions.push(subscription);
    return subscription;
  }

  // Clean up all subscriptions
  dispose(): void {
    this.subscriptions.forEach(subscription => {
      if (!subscription.closed) {
        subscription.unsubscribe();
      }
    });
    this.subscriptions = [];
    this.subject.complete();
    this.logger.info('Event emitter disposed');
  }

  [Symbol.dispose](): void {
    this.dispose();
  }
}