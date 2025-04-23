// src/state/connection-state.ts
import { BehaviorSubject, Observable } from 'rxjs';
import { map, distinctUntilChanged } from 'rxjs/operators';

import { getLogger } from '../boot/logging';

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
export class ConnectionStateService {
  private logger = getLogger('ConnectionStateService');
  
  private state$ = new BehaviorSubject<ConnectionState>(initialConnectionState);

  // Select a slice of the connection state
  select<T>(selector: (state: ConnectionState) => T): Observable<T> {
    return this.state$.pipe(
      map(selector),
      distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))
    );
  }

  // Get the entire connection state as an observable
  getState$(): Observable<ConnectionState> {
    return this.state$.asObservable();
  }

  // Get the current state snapshot
  getState(): ConnectionState {
    return this.state$.getValue();
  }

  // Update the connection state
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

    this.logger.debug('Updating connection state', changes);
    this.state$.next(newState);
  }

  // Calculate connection quality based on latency
  calculateConnectionQuality(latency: number | null): ConnectionQuality {
    if (latency === null || latency < 0) return ConnectionQuality.UNKNOWN;
    if (latency <= 250) return ConnectionQuality.GOOD;
    if (latency <= 750) return ConnectionQuality.DEGRADED;
    return ConnectionQuality.POOR;
  }
}

// Export singleton instance
export const connectionState = new ConnectionStateService();