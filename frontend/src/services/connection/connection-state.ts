export type ConnectionQuality = 'good' | 'degraded' | 'poor';

export interface ConnectionState {
  isConnected: boolean;
  isConnecting: boolean;
  connectionQuality: ConnectionQuality;
  lastHeartbeatTime: number;
  heartbeatLatency: number | null;
  missedHeartbeats: number;
  error: string | null;
  circuitBreakerState: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
}

export class ConnectionStateManager {
  private state: ConnectionState;

  constructor() {
    this.state = {
      isConnected: false,
      isConnecting: false,
      connectionQuality: 'good',
      lastHeartbeatTime: 0,
      heartbeatLatency: null,
      missedHeartbeats: 0,
      error: null,
      circuitBreakerState: 'CLOSED'
    };
  }

  public updateState(updates: Partial<ConnectionState>): ConnectionState {
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
      connectionQuality: 'good',
      lastHeartbeatTime: 0,
      heartbeatLatency: null,
      missedHeartbeats: 0,
      error: null,
      circuitBreakerState: 'CLOSED'
    };
  }
}