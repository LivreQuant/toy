// src/hooks/useSimulatorState.ts
import { useSimulatorState as useStateContext } from '../contexts/SimulatorStateContext';
import { simulatorState } from '../state/simulator-state';

export function useSimulatorState() {
  const state = useStateContext();
  
  return {
    // State values
    status: state.status,
    isLoading: state.isLoading,
    error: state.error,
    lastUpdated: state.lastUpdated,
    
    // State derivations
    isRunning: state.status === 'RUNNING',
    isStopped: state.status === 'STOPPED',
    isStarting: state.status === 'STARTING',
    isStopping: state.status === 'STOPPING',
    isError: state.status === 'ERROR',
    
    // Update methods
    setStatus: simulatorState.setStatus.bind(simulatorState),
    startLoading: simulatorState.startLoading.bind(simulatorState),
    endLoading: simulatorState.endLoading.bind(simulatorState),
    updateState: simulatorState.updateState.bind(simulatorState)
  };
}