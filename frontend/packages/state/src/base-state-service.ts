// src/base-state-service.ts
import { BehaviorSubject, Observable } from 'rxjs';
import { map, distinctUntilChanged } from 'rxjs/operators';
import { getLogger } from '@trading-app/logging';

/**
 * Base class for state management services
 * Provides common functionality for state management with RxJS
 */
export abstract class BaseStateService<T> {
  protected logger = getLogger(this.constructor.name);
  protected state$: BehaviorSubject<T>;

  constructor(initialState: T) {
    this.state$ = new BehaviorSubject<T>(initialState);
  }

  /**
   * Select a slice of the state
   * @param selector - Function to select part of the state
   * @returns Observable of the selected state slice
   */
  select<K>(selector: (state: T) => K): Observable<K> {
    return this.state$.pipe(
      map(selector),
      distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))
    );
  }

  /**
   * Get the entire state as an observable
   */
  getState$(): Observable<T> {
    return this.state$.asObservable();
  }

  /**
   * Get the current state snapshot
   */
  getState(): T {
    return this.state$.getValue();
  }

  /**
   * Update the state with partial changes
   * @param changes - Partial state changes to apply
   */
  updateState(changes: Partial<T>): void {
    const currentState = this.getState();
    const newState: T = {
      ...currentState,
      ...changes
    };
    
    this.logger.debug('Updating state', { changes });
    this.state$.next(newState);
  }

  /**
   * Replace the entire state
   * @param newState - The new state to set
   */
  setState(newState: T): void {
    this.logger.debug('Setting new state', { newState });
    this.state$.next(newState);
  }

  /**
   * Reset state to initial state
   */
  abstract reset(): void;

  /**
   * Clean up resources
   */
  dispose(): void {
    this.state$.complete();
  }
}