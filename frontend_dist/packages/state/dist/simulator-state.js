// src/simulator-state.ts
import { BaseStateService } from './base-state-service';
// Initial simulator state
export const initialSimulatorState = {
    status: 'UNKNOWN',
    isLoading: false,
    error: null,
    lastUpdated: 0,
};
// Simulator state service
export class SimulatorStateService extends BaseStateService {
    constructor() {
        super(initialSimulatorState);
    }
    // Override updateState to always update lastUpdated
    updateState(changes) {
        super.updateState(Object.assign(Object.assign({}, changes), { lastUpdated: Date.now() }));
    }
    // Set simulator status
    setStatus(status, error) {
        this.updateState({
            status,
            error: error || null,
            isLoading: false
        });
    }
    // Start loading state
    startLoading() {
        this.updateState({ isLoading: true });
    }
    // End loading state
    endLoading(error) {
        this.updateState({
            isLoading: false,
            error: error || null
        });
    }
    reset() {
        this.setState(initialSimulatorState);
    }
}
// Export singleton instance
export const simulatorState = new SimulatorStateService();
