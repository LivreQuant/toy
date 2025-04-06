// src/services/connection/unified-connection-state.ts
import { EventEmitter } from '../../utils/event-emitter';
import { Logger } from '../../utils/logger';

export enum ConnectionServiceType {
  WEBSOCKET = 'websocket',
  REST = 'rest' // Keeping REST for API health tracking
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
  POOR = 'poor',
  UNKNOWN = 'unknown'
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
  private overallQuality: ConnectionQuality = ConnectionQuality.UNKNOWN;
  private simulatorStatus: string = 'UNKNOWN';
  private isRecovering: boolean = false;
  private recoveryAttempt: number = 0;
  private lastHeartbeatTime: number = 0;
  private heartbeatLatency: number | null = null;
  private primaryService: ConnectionServiceType = ConnectionServiceType.WEBSOCKET;
  private logger: Logger;

  constructor(logger: Logger) {
    super();
    this.logger = logger.createChild('UnifiedState');
    this.logger.info('Initializing UnifiedConnectionState');

    // Initialize service states
    this.initializeServiceState(ConnectionServiceType.WEBSOCKET);
    // Initialize REST state if needed
    // this.initializeServiceState(ConnectionServiceType.REST);
  }

  private initializeServiceState(service: ConnectionServiceType): void {
     this.serviceStates.set(service, {
      status: ConnectionStatus.DISCONNECTED,
      lastConnected: null,
      error: null,
      recoveryAttempts: 0
    });
  }

  public updateServiceState(
    service: ConnectionServiceType,
    updates: Partial<ServiceState>
  ): void {
    const currentState = this.serviceStates.get(service);
    if (!currentState) {
        this.logger.error(`Attempted to update state for uninitialized service: ${service}`);
        return;
    }

    const hasChanged = Object.keys(updates).some(key =>
        currentState[key as keyof ServiceState] !== updates[key as keyof ServiceState]
    );

    if (!hasChanged) {
        return;
    }

    const newState = { ...currentState, ...updates };
    this.serviceStates.set(service, newState);
    this.logger.info(`State updated for service: ${service}`, { newStatus: newState.status, error: newState.error });

    if (service === this.primaryService) {
      this.updateOverallStatus();
    }

    this.emit(`${service}_state_change`, { service, state: newState });
    this.emit('state_change', this.getState());
  }

  public updateSimulatorStatus(status: string): void {
    if (this.simulatorStatus !== status) {
      this.logger.info(`Simulator status changed: ${this.simulatorStatus} -> ${status}`);
      this.simulatorStatus = status;
      this.emit('simulator_status_change', { status });
      this.emit('state_change', this.getState());
    }
  }

  public updateRecovery(isRecovering: boolean, attempt: number = 0): void {
    const changed = this.isRecovering !== isRecovering || this.recoveryAttempt !== attempt;

    this.isRecovering = isRecovering;
    this.recoveryAttempt = attempt;

    if (changed) {
      this.logger.info(`Recovery state changed: isRecovering=${isRecovering}, attempt=${attempt}`);
      this.updateOverallStatus();
      this.emit('recovery_change', { isRecovering, attempt });
      this.emit('state_change', this.getState());
    }
  }

  public updateHeartbeat(timestamp: number, latency: number): void {
    this.lastHeartbeatTime = timestamp;
    this.heartbeatLatency = latency;

    const newQuality = this.calculateConnectionQuality(latency);

    if (newQuality !== this.overallQuality) {
       this.logger.info(`Connection quality changed: ${this.overallQuality} -> ${newQuality} (Latency: ${latency}ms)`);
      this.overallQuality = newQuality;
      this.emit('quality_change', { quality: newQuality });
      this.emit('state_change', this.getState());
    }
  }

  private calculateConnectionQuality(latency: number): ConnectionQuality {
    if (latency < 0) return ConnectionQuality.UNKNOWN;
    if (latency <= 250) return ConnectionQuality.GOOD;
    if (latency <= 750) return ConnectionQuality.DEGRADED;
    return ConnectionQuality.POOR;
  }

  private updateOverallStatus(): void {
    const primaryState = this.serviceStates.get(this.primaryService);
    if (!primaryState) {
        this.logger.error("Cannot update overall status: Primary service state not found.");
        return;
    }

    let newOverallStatus: ConnectionStatus;

    if (this.isRecovering) {
        newOverallStatus = ConnectionStatus.RECOVERING;
    } else {
        newOverallStatus = primaryState.status;
    }

    if (newOverallStatus !== this.overallStatus) {
       this.logger.info(`Overall connection status changed: ${this.overallStatus} -> ${newOverallStatus}`);
      this.overallStatus = newOverallStatus;
      this.emit('status_change', { status: newOverallStatus });
    }
  }

  public getServiceState(service: ConnectionServiceType): ServiceState {
    const state = this.serviceStates.get(service);
    if (state) {
        return { ...state };
    }
    this.logger.error(`Requested state for uninitialized service: ${service}. Returning default.`);
    return {
      status: ConnectionStatus.DISCONNECTED,
      lastConnected: null,
      error: 'Service not initialized',
      recoveryAttempts: 0
    };
  }

  public getState() {
    return {
      isConnected: this.overallStatus === ConnectionStatus.CONNECTED,
      isConnecting: this.overallStatus === ConnectionStatus.CONNECTING,
      isRecovering: this.isRecovering,
      recoveryAttempt: this.recoveryAttempt,
      connectionQuality: this.overallQuality,
      simulatorStatus: this.simulatorStatus,
      webSocketState: this.getServiceState(ConnectionServiceType.WEBSOCKET),
      // Removed SSE state
      lastHeartbeatTime: this.lastHeartbeatTime,
      heartbeatLatency: this.heartbeatLatency,
      overallStatus: this.overallStatus
    };
  }

  public reset(): void {
    this.logger.warn('Resetting all connection states.');
    this.serviceStates.forEach((_, service) => {
      this.updateServiceState(service, {
        status: ConnectionStatus.DISCONNECTED,
        lastConnected: null,
        error: 'State reset',
        recoveryAttempts: 0
      });
    });

    this.overallQuality = ConnectionQuality.UNKNOWN;
    this.isRecovering = false;
    this.recoveryAttempt = 0;
    this.lastHeartbeatTime = 0;
    this.heartbeatLatency = null;

    this.emit('state_change', this.getState());
  }

  public dispose(): void {
    this.logger.warn('Disposing UnifiedConnectionState.');
    this.removeAllListeners();
  }
}