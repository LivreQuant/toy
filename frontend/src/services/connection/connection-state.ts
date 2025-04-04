// src/services/connection/connection-state.ts
export type ConnectionQuality = 'good' | 'degraded' | 'poor';

export interface ConnectionState {
  isConnected: boolean;
  isConnecting: boolean;
  sessionId: string | null;
  connectionQuality: ConnectionQuality;
  lastHeartbeatTime: number;
  heartbeatLatency: number | null;
  missedHeartbeats: number;
  error: string | null;
  circuitBreakerState: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
  simulatorId: string | null;
  simulatorStatus: string;
}

export class ConnectionStateManager {
  private state: ConnectionState;

  constructor() {
    this.state = {
      isConnected: false,
      isConnecting: false,
      sessionId: null,
      connectionQuality: 'good',
      lastHeartbeatTime: 0,
      heartbeatLatency: null,
      missedHeartbeats: 0,
      error: null,
      circuitBreakerState: 'CLOSED',
      simulatorId: null,
      simulatorStatus: 'UNKNOWN'
    };
  }

  public updateState(updates: Partial<ConnectionState>): void {
    const prevState = { ...this.state };
    this.state = { ...this.state, ...updates };
    return this.state;
  }

  public getState(): ConnectionState {
    return { ...this.state };
  }

  public reset(): void {
    this.state = {
      isConnected: false,
      isConnecting: false,
      sessionId: null,
      connectionQuality: 'good',
      lastHeartbeatTime: 0,
      heartbeatLatency: null,
      missedHeartbeats: 0,
      error: null,
      circuitBreakerState: 'CLOSED',
      simulatorId: null,
      simulatorStatus: 'UNKNOWN'
    };
  }
}