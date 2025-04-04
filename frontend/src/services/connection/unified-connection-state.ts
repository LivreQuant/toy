// src/services/connection/unified-connection-state.ts
import { EventEmitter } from '../../utils/event-emitter';

export enum ConnectionServiceType {
  WEBSOCKET = 'websocket',
  SSE = 'sse',
  REST = 'rest'
}

export enum ConnectionStatus {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  RECOVERING = 'recovering'
}

export enum ConnectionQuality {
  GOOD = 'good',
  DEGRADED = 'degraded',
  POOR = 'poor'
}

export interface ServiceState {
  status: ConnectionStatus;
  lastConnected: number | null;
  error: string | null;
  recoveryAttempts: number;
}

export class UnifiedConnectionState extends EventEmitter {
  private serviceStates: Map<ConnectionServiceType, ServiceState> = new Map();
  private overallStatus: ConnectionStatus = ConnectionStatus.DISCONNECTED;
  private overallQuality: ConnectionQuality = ConnectionQuality.GOOD;
  private simulatorStatus: string = 'UNKNOWN';
  private isRecovering: boolean = false;
  private recoveryAttempt: number = 0;
  private lastHeartbeatTime: number = 0;
  private heartbeatLatency: number | null = null;
  private primaryService: ConnectionServiceType = ConnectionServiceType.WEBSOCKET;
  
  constructor() {
    super();
    
    // Initialize service states
    this.serviceStates.set(ConnectionServiceType.WEBSOCKET, {
      status: ConnectionStatus.DISCONNECTED,
      lastConnected: null,
      error: null,
      recoveryAttempts: 0
    });
    
    this.serviceStates.set(ConnectionServiceType.SSE, {
      status: ConnectionStatus.DISCONNECTED,
      lastConnected: null,
      error: null,
      recoveryAttempts: 0
    });
  }
  
  // Update the state of a specific service
  public updateServiceState(
    service: ConnectionServiceType,
    updates: Partial<ServiceState>
  ): void {
    const currentState = this.serviceStates.get(service) || {
      status: ConnectionStatus.DISCONNECTED,
      lastConnected: null,
      error: null,
      recoveryAttempts: 0
    };
    
    const newState = { ...currentState, ...updates };
    this.serviceStates.set(service, newState);
    
    // If this is the primary service, update overall status accordingly
    if (service === this.primaryService) {
      this.updateOverallState();
    }
    
    // Emit service-specific state change event
    this.emit(`${service}_state_change`, { service, state: newState });
    this.emit('state_change', this.getState());
  }
  
  // Update the simulator status
  public updateSimulatorStatus(status: string): void {
    if (this.simulatorStatus !== status) {
      this.simulatorStatus = status;
      this.emit('simulator_status_change', { status });
      this.emit('state_change', this.getState());
    }
  }
  
  // Update recovery information
  public updateRecovery(isRecovering: boolean, attempt: number = 0): void {
    const changed = this.isRecovering !== isRecovering || this.recoveryAttempt !== attempt;
    
    this.isRecovering = isRecovering;
    this.recoveryAttempt = attempt;
    
    if (changed) {
      this.emit('recovery_change', { isRecovering, attempt });
      this.emit('state_change', this.getState());
    }
  }
  
  // Update heartbeat information
  public updateHeartbeat(timestamp: number, latency: number): void {
    this.lastHeartbeatTime = timestamp;
    this.heartbeatLatency = latency;
    
    // Determine connection quality based on latency
    const newQuality = this.calculateConnectionQuality(latency);
    
    if (newQuality !== this.overallQuality) {
      this.overallQuality = newQuality;
      this.emit('quality_change', { quality: newQuality });
      this.emit('state_change', this.getState());
    }
  }
  
  // Calculate connection quality based on latency
  private calculateConnectionQuality(latency: number): ConnectionQuality {
    if (latency <= 200) return ConnectionQuality.GOOD;
    if (latency <= 500) return ConnectionQuality.DEGRADED;
    return ConnectionQuality.POOR;
  }
  
  // Update the overall connection state based on services
  private updateOverallState(): void {
    const primaryState = this.serviceStates.get(this.primaryService);
    
    if (!primaryState) return;
    
    const newStatus = primaryState.status;
    
    if (newStatus !== this.overallStatus) {
      this.overallStatus = newStatus;
      this.emit('status_change', { status: newStatus });
      this.emit('state_change', this.getState());
    }
  }
  
  // Get the current state of a specific service
  public getServiceState(service: ConnectionServiceType): ServiceState {
    return this.serviceStates.get(service) || {
      status: ConnectionStatus.DISCONNECTED,
      lastConnected: null,
      error: null,
      recoveryAttempts: 0
    };
  }
  
  // Get the complete current state
  public getState() {
    return {
      isConnected: this.overallStatus === ConnectionStatus.CONNECTED,
      isConnecting: this.overallStatus === ConnectionStatus.CONNECTING,
      isRecovering: this.isRecovering,
      recoveryAttempt: this.recoveryAttempt,
      connectionQuality: this.overallQuality,
      simulatorStatus: this.simulatorStatus,
      webSocketState: this.getServiceState(ConnectionServiceType.WEBSOCKET),
      sseState: this.getServiceState(ConnectionServiceType.SSE),
      lastHeartbeatTime: this.lastHeartbeatTime,
      heartbeatLatency: this.heartbeatLatency
    };
  }
  
  // Reset all state values
  public reset(): void {
    this.serviceStates.forEach((_, service) => {
      this.updateServiceState(service, {
        status: ConnectionStatus.DISCONNECTED,
        lastConnected: null,
        error: null,
        recoveryAttempts: 0
      });
    });
    
    this.overallStatus = ConnectionStatus.DISCONNECTED;
    this.overallQuality = ConnectionQuality.GOOD;
    this.isRecovering = false;
    this.recoveryAttempt = 0;
    this.lastHeartbeatTime = 0;
    this.heartbeatLatency = null;
    
    this.emit('state_change', this.getState());
  }
}