// src/state/simulator-state.ts
import { BehaviorSubject, Observable } from 'rxjs';
import { map, distinctUntilChanged } from 'rxjs/operators';
import { getLogger } from '../boot/logging';

export type SimulatorStatus = 'RUNNING' | 'STOPPED' | 'STARTING' | 'STOPPING' | 'ERROR' | 'UNKNOWN';

// Define the simulator state interface
export interface SimulatorState {
  status: SimulatorStatus;
  isLoading: boolean;
  error: string | null;
  lastUpdated: number;
}

// Initial simulator state
export const initialSimulatorState: SimulatorState = {
  status: 'UNKNOWN',
  isLoading: false,
  error: null,
  lastUpdated: 0,
};

// Simulator state service
export class SimulatorStateService {
  private state$ = new BehaviorSubject<SimulatorState>(initialSimulatorState);
  private logger = getLogger('SimulatorStateService');

  // Select a slice of the simulator state
  select<T>(selector: (state: SimulatorState) => T): Observable<T> {
    return this.state$.pipe(
      map(selector),
      distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))
    );
  }

  // Get the entire simulator state as an observable
  getState$(): Observable<SimulatorState> {
    return this.state$.asObservable();
  }

  // Get the current state snapshot
  getState(): SimulatorState {
    return this.state$.getValue();
  }

  // Update the simulator state
  updateState(changes: Partial<SimulatorState>): void {
    const currentState = this.getState();
    const newState: SimulatorState = {
      ...currentState,
      ...changes,
      lastUpdated: Date.now()
    };
    
    this.logger.debug('Updating simulator state', changes);
    this.state$.next(newState);
  }

  // Set simulator status
  setStatus(status: SimulatorStatus, error?: string): void {
    this.updateState({
      status,
      error: error || null,
      isLoading: false
    });
  }

  // Start loading state
  startLoading(): void {
    this.updateState({ isLoading: true });
  }

  // End loading state
  endLoading(error?: string): void {
    this.updateState({ 
      isLoading: false,
      error: error || null
    });
  }
}

// Export singleton instance
export const simulatorState = new SimulatorStateService();