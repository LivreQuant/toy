// src/simulator-state.ts
import { BaseStateService } from './base-state-service';

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
export class SimulatorStateService extends BaseStateService<SimulatorState> {
  constructor() {
    super(initialSimulatorState);
  }

  // Override updateState to always update lastUpdated
  updateState(changes: Partial<SimulatorState>): void {
    super.updateState({
      ...changes,
      lastUpdated: Date.now()
    });
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

  reset(): void {
    this.setState(initialSimulatorState);
  }
}

// Export singleton instance
export const simulatorState = new SimulatorStateService();