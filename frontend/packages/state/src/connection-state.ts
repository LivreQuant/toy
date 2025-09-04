// src/connection-state.ts
import { BaseStateService } from './base-state-service';

// Define enums for connection status
export enum ConnectionStatus {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  RECOVERING = 'recovering'
}

export enum ConnectionQuality {
  GOOD = 'good',
  DEGRADED = 'degraded',
  POOR = 'poor',
  UNKNOWN = 'unknown'
}

// Define the connection state interface
export interface ConnectionState {
  overallStatus: ConnectionStatus;
  webSocketStatus: ConnectionStatus;
  quality: ConnectionQuality;
  isRecovering: boolean;
  recoveryAttempt: number;
  lastHeartbeatTime?: number;
  heartbeatLatency?: number | null;
  simulatorStatus: string;
  lastConnectionError: string | null;
}

// Initial connection state
export const initialConnectionState: ConnectionState = {
  overallStatus: ConnectionStatus.DISCONNECTED,
  webSocketStatus: ConnectionStatus.DISCONNECTED,
  quality: ConnectionQuality.UNKNOWN,
  isRecovering: false,
  recoveryAttempt: 0,
  simulatorStatus: 'UNKNOWN',
  lastConnectionError: null,
};

// Connection state service
export class ConnectionStateService extends BaseStateService<ConnectionState> {
  constructor() {
    super(initialConnectionState);
  }

  // Override updateState to handle overall status calculation
  updateState(changes: Partial<ConnectionState>): void {
    const currentState = this.getState();
    
    // Recalculate overall status if specific statuses change
    let newOverallStatus = changes.overallStatus ?? currentState.overallStatus;

    if (changes.webSocketStatus || changes.isRecovering !== undefined) {
        const wsStatus = changes.webSocketStatus ?? currentState.webSocketStatus;
        const isRecovering = changes.isRecovering ?? currentState.isRecovering;

        if (isRecovering) {
            newOverallStatus = ConnectionStatus.RECOVERING;
        } else {
            newOverallStatus = wsStatus;
        }
    }

    // Update the state with computed overall status
    const newState: ConnectionState = {
        ...currentState,
        ...changes,
        overallStatus: newOverallStatus
    };

    this.logger.debug('Updating connection state', {
        changes,
        newOverallStatus,
        currentOverallStatus: currentState.overallStatus
    });
    
    this.state$.next(newState);
  }

  // Calculate connection quality based on latency
  calculateConnectionQuality(latency: number | null): ConnectionQuality {
    if (latency === null || latency < 0) return ConnectionQuality.UNKNOWN;
    if (latency <= 250) return ConnectionQuality.GOOD;
    if (latency <= 750) return ConnectionQuality.DEGRADED;
    return ConnectionQuality.POOR;
  }

  // Reset to initial state
  reset(): void {
    this.setState(initialConnectionState);
  }
}

// Export singleton instance
export const connectionState = new ConnectionStateService();