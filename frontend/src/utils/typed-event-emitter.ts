// src/utils/typed-event-emitter.ts
import { Subject, Observable, Subscription } from 'rxjs';
import { filter, map, take } from 'rxjs/operators';
import { Disposable } from './disposable';
import { EnhancedLogger } from './enhanced-logger';
import { getLogger } from '../boot/logging'; // Assuming constructor injection fix is kept

export type EventMap = Record<string, any>;

interface EventObject<Payload = any, Type extends string = string> {
  type: Type;
  payload: Payload;
}

export class TypedEventEmitter<T extends EventMap> implements Disposable {
  protected logger: EnhancedLogger;
  private _isDisposed: boolean = false;
  private subject$ = new Subject<EventObject<T[keyof T], string>>();
  private internalSubscriptions = new Subscription();

  // Constructor accepts logger instance
  constructor(loggerInstance: EnhancedLogger) {
    this.logger = loggerInstance;
  }

  protected get isDisposed(): boolean {
      return this._isDisposed;
  }

  emit<K extends string & keyof T>(type: K, payload: T[K]): void {
    if (this.isDisposed) {
        this.logger.debug(`Emit skipped for "${type}": Disposed.`);
        return;
    }
    const logPayload = payload === undefined ? '<undefined>' : payload;
    this.logger.debug(`Emitting event: "${type}"`, { payload: logPayload });
    this.subject$.next({ type: type, payload });
  }

  on<K extends string & keyof T>(type: K): Observable<T[K]> {
      return this.subject$.pipe(
          filter((event): event is EventObject<T[K], K> => event.type === type),
          map(event => event.payload)
      );
  }


  subscribe<K extends string & keyof T>(type: K, handler: (payload: T[K]) => void): Subscription {
    if (this.isDisposed) return new Subscription();
    const subscription = this.on(type).subscribe({
        next: (payload) => {
            try {
                 handler(payload);
             } catch (error: any) {
                 // FIX: Restore logger arguments
                 this.logger.error(`Error in event handler for "${type}"`, { error: error.message, handlerName: handler.name });
             }
        },
        error: (err) => {
             // FIX: Restore logger arguments
             this.logger.error(`Error in event subscription for "${type}"`, { error: err });
         }
    });
    this.internalSubscriptions.add(subscription);
    return subscription;
  }

  once<K extends string & keyof T>(type: K, handler: (payload: T[K]) => void): Subscription {
     if (this.isDisposed) return new Subscription();
     const subscription = this.on(type).pipe(take(1)).subscribe({
         next: (payload) => {
             try {
                 handler(payload);
             } catch (error: any) {
                  // FIX: Restore logger arguments
                 this.logger.error(`Error in one-time event handler for "${type}"`, { error: error.message, handlerName: handler.name });
             }
         },
         error: (err) => {
             // FIX: Restore logger arguments
            this.logger.error(`Error in one-time event subscription for "${type}"`, { error: err });
         }
     });
     this.internalSubscriptions.add(subscription);
     return subscription;
   }

   removeAllListeners(): void {
       if (!this.internalSubscriptions.closed) {
           this.logger.debug(`Removing all (${this.internalSubscriptions.closed ? 0 : 'active'}) listeners.`);
           this.internalSubscriptions.unsubscribe();
           this.internalSubscriptions = new Subscription();
       }
   }

   dispose(): void {
       if (this.isDisposed) return;
       this._isDisposed = true;
       this.logger.info('Disposing TypedEventEmitter...');
       this.removeAllListeners();
       this.subject$.complete();
       this.logger.info('TypedEventEmitter disposed.');
   }

   [Symbol.dispose](): void {
       this.dispose();
   }
}