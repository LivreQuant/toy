// src/base-state-service.ts
import { BehaviorSubject } from 'rxjs';
import { map, distinctUntilChanged } from 'rxjs/operators';
import { getLogger } from '@trading-app/logging';
/**
 * Base class for state management services
 * Provides common functionality for state management with RxJS
 */
export class BaseStateService {
    constructor(initialState) {
        this.logger = getLogger(this.constructor.name);
        this.state$ = new BehaviorSubject(initialState);
    }
    /**
     * Select a slice of the state
     * @param selector - Function to select part of the state
     * @returns Observable of the selected state slice
     */
    select(selector) {
        return this.state$.pipe(map(selector), distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr)));
    }
    /**
     * Get the entire state as an observable
     */
    getState$() {
        return this.state$.asObservable();
    }
    /**
     * Get the current state snapshot
     */
    getState() {
        return this.state$.getValue();
    }
    /**
     * Update the state with partial changes
     * @param changes - Partial state changes to apply
     */
    updateState(changes) {
        const currentState = this.getState();
        const newState = Object.assign(Object.assign({}, currentState), changes);
        this.logger.debug('Updating state', { changes });
        this.state$.next(newState);
    }
    /**
     * Replace the entire state
     * @param newState - The new state to set
     */
    setState(newState) {
        this.logger.debug('Setting new state', { newState });
        this.state$.next(newState);
    }
    /**
     * Clean up resources
     */
    dispose() {
        this.state$.complete();
    }
}
