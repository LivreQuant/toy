// src/hooks/useConnectionState.ts
import { useConnectionState as useStateContext } from '../contexts/ConnectionStateContext';
import { connectionState, ConnectionStatus, ConnectionQuality } from '@trading-app/state';

export function useConnectionState() {
  const state = useStateContext();
  
  return {
    // State values
    status: state.overallStatus,
    webSocketStatus: state.webSocketStatus,
    quality: state.quality,
    isConnected: state.overallStatus === ConnectionStatus.CONNECTED,
    isConnecting: state.overallStatus === ConnectionStatus.CONNECTING,
    isRecovering: state.isRecovering,
    recoveryAttempt: state.recoveryAttempt,
    simulatorStatus: state.simulatorStatus,
    lastError: state.lastConnectionError,
    
    // State derivations - ✅ FIX: Update to handle 'CONNECTED' status
    isSimulatorRunning: state.simulatorStatus === 'RUNNING' || state.simulatorStatus === 'CONNECTED',
    isSimulatorBusy: state.simulatorStatus === 'STARTING' || state.simulatorStatus === 'STOPPING',
    
    // Helpers
    isGoodQuality: state.quality === ConnectionQuality.GOOD,
    latency: state.heartbeatLatency,
    
    // Update methods
    updateState: connectionState.updateState.bind(connectionState)
  };
}