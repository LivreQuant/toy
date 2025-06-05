import { BaseStateService } from './base-state-service';
export type SimulatorStatus = 'RUNNING' | 'STOPPED' | 'STARTING' | 'STOPPING' | 'ERROR' | 'UNKNOWN';
export interface SimulatorState {
    status: SimulatorStatus;
    isLoading: boolean;
    error: string | null;
    lastUpdated: number;
}
export declare const initialSimulatorState: SimulatorState;
export declare class SimulatorStateService extends BaseStateService<SimulatorState> {
    constructor();
    updateState(changes: Partial<SimulatorState>): void;
    setStatus(status: SimulatorStatus, error?: string): void;
    startLoading(): void;
    endLoading(error?: string): void;
    reset(): void;
}
export declare const simulatorState: SimulatorStateService;
