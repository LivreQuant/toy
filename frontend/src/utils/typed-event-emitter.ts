// src/utils/typed-event-emitter.ts
import { Subject, Observable, Subscription } from 'rxjs';
import { filter, map, take } from 'rxjs/operators';
import { Disposable } from './disposable';
import { EnhancedLogger } from './enhanced-logger';
import { getLogger } from '../boot/logging';

export type EventMap = Record<string, any>;

// Payload can be any type, Type must be a string key derived from an EventMap
interface EventObject<Payload = any, Type extends string = string> {
  type: Type;
  payload: Payload;
}


export class TypedEventEmitter<T extends EventMap> implements Disposable {
  // Use string as default key type for flexibility, enforce T keys in methods
  private subject$ = new Subject<EventObject<T[keyof T], string>>();
  private internalSubscriptions = new Subscription();
  // FIX: Make logger protected
  protected logger: EnhancedLogger;
  private isDisposed = false;

  constructor(loggerName?: string) {
    this.logger = getLogger(loggerName || 'TypedEventEmitter');
  }

  // Ensure type K is constrained to string keys of T
  emit<K extends string & keyof T>(type: K, payload: T[K]): void {
    if (this.isDisposed) {
        this.logger.debug(`Emit skipped for "${type}": Disposed.`);
        return;
    }
    this.logger.debug(`Emitting event: "${type}"`, { payload: payload === undefined ? '<undefined>' : payload });
    this.subject$.next({ type: type, payload });
  }

  // Ensure type K is constrained to string keys of T
  on<K extends string & keyof T>(type: K): Observable<T[K]> {
    // Ensure correct type assertion in filter
    return this.subject$.pipe(
      filter((event): event is EventObject<T[K], K> => event.type === type),
      map(event => event.payload)
    );
  }

  // Ensure type K is constrained to string keys of T
  subscribe<K extends string & keyof T>(type: K, handler: (payload: T[K]) => void): Subscription {
    if (this.isDisposed) return new Subscription(); // Return empty subscription if disposed
    const subscription = this.on(type).subscribe({
        next: (payload) => {
            try {
                handler(payload);
            } catch (error: any) {
                this.logger.error(`Error in event handler for "${type}"`, { error: error.message, handlerName: handler.name });
            }
        },
        error: (err) => {
            // Should not typically happen with BehaviorSubject unless source errors
            this.logger.error(`Error in event subscription for "${type}"`, { error: err });
        }
    });
    this.internalSubscriptions.add(subscription); // Track subscription for disposal
    return subscription;
  }

  // Ensure type K is constrained to string keys of T
  once<K extends string & keyof T>(type: K, handler: (payload: T[K]) => void): Subscription {
     if (this.isDisposed) return new Subscription();
     const subscription = this.on(type).pipe(take(1)).subscribe({
         next: (payload) => {
             try {
                 handler(payload);
             } catch (error: any) {
                 this.logger.error(`Error in one-time event handler for "${type}"`, { error: error.message, handlerName: handler.name });
             }
         },
         error: (err) => {
            this.logger.error(`Error in one-time event subscription for "${type}"`, { error: err });
         }
     });
     // Also track 'once' subscriptions for cleanup during dispose
     this.internalSubscriptions.add(subscription);
     return subscription;
   }

   /** Removes all internally tracked subscriptions added via .subscribe() or .once() */
   removeAllListeners(): void {
       if (!this.internalSubscriptions.closed) {
           this.logger.debug(`Removing all (${this.internalSubscriptions.closed ? 0 : 'active'}) listeners.`);
           this.internalSubscriptions.unsubscribe();
           // Recreate for potential future subscriptions after explicit removal
           this.internalSubscriptions = new Subscription();
       }
   }

   /** Cleans up resources: completes the subject and unsubscribes listeners. */
   dispose(): void {
       if (this.isDisposed) return;
       this.isDisposed = true;
       this.logger.info('Disposing TypedEventEmitter...');
       this.removeAllListeners(); // Unsubscribe all active listeners
       this.subject$.complete(); // Complete the subject
       this.logger.info('TypedEventEmitter disposed.');
   }

   /** Implements the Disposable pattern using Symbol.dispose */
   [Symbol.dispose](): void {
       this.dispose();
   }
}