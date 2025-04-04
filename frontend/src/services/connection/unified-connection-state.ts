// src/services/connection/unified-connection-state.ts
import { EventEmitter } from '../../utils/event-emitter';
import { Logger } from '../../utils/logger'; // Import Logger

// --- Enums (Keep as before) ---
export enum ConnectionServiceType {
  WEBSOCKET = 'websocket',
  SSE = 'sse',
  REST = 'rest' // Although REST is request/response, might track API health
}

export enum ConnectionStatus {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  RECOVERING = 'recovering' // Explicit state for recovery attempts
}

export enum ConnectionQuality {
  GOOD = 'good',
  DEGRADED = 'degraded',
  POOR = 'poor',
  UNKNOWN = 'unknown' // Added unknown state
}

// --- Interface (Export this) ---
export interface ServiceState {
  status: ConnectionStatus;
  lastConnected: number | null;
  error: string | null;
  recoveryAttempts: number;
}

/**
 * Manages and aggregates the connection state for multiple services (WebSocket, SSE).
 * Provides a unified view of the overall connection status and quality.
 */
export class UnifiedConnectionState extends EventEmitter {
  private serviceStates: Map<ConnectionServiceType, ServiceState> = new Map();
  private overallStatus: ConnectionStatus = ConnectionStatus.DISCONNECTED;
  private overallQuality: ConnectionQuality = ConnectionQuality.UNKNOWN; // Start as unknown
  private simulatorStatus: string = 'UNKNOWN';
  private isRecovering: boolean = false;
  private recoveryAttempt: number = 0;
  private lastHeartbeatTime: number = 0;
  private heartbeatLatency: number | null = null;
  private primaryService: ConnectionServiceType = ConnectionServiceType.WEBSOCKET;
  private logger: Logger; // Add logger

  constructor(logger: Logger) { // Accept logger
    super();
    this.logger = logger.createChild('UnifiedState'); // Use createChild if implemented, otherwise just use logger
    this.logger.info('Initializing UnifiedConnectionState');

    // Initialize service states
    this.initializeServiceState(ConnectionServiceType.WEBSOCKET);
    this.initializeServiceState(ConnectionServiceType.SSE);
    // Initialize REST state if needed (e.g., for API health)
    // this.initializeServiceState(ConnectionServiceType.REST);
  }

  // Helper to initialize state for a service
  private initializeServiceState(service: ConnectionServiceType): void {
     this.serviceStates.set(service, {
      status: ConnectionStatus.DISCONNECTED,
      lastConnected: null,
      error: null,
      recoveryAttempts: 0
    });
  }

  /**
   * Updates the state for a specific connection service.
   * @param service - The type of service being updated.
   * @param updates - An object containing the state properties to update.
   */
  public updateServiceState(
    service: ConnectionServiceType,
    updates: Partial<ServiceState>
  ): void {
    const currentState = this.serviceStates.get(service);
    if (!currentState) {
        this.logger.error(`Attempted to update state for uninitialized service: ${service}`);
        return;
    }

    // Prevent unnecessary updates if state hasn't changed
    const hasChanged = Object.keys(updates).some(key =>
        currentState[key as keyof ServiceState] !== updates[key as keyof ServiceState]
    );

    if (!hasChanged) {
        // this.logger.info(`Skipping state update for ${service}, no changes detected.`);
        return;
    }


    const newState = { ...currentState, ...updates };
    this.serviceStates.set(service, newState);
    this.logger.info(`State updated for service: ${service}`, { newStatus: newState.status, error: newState.error });


    // If this is the primary service, update overall status accordingly
    if (service === this.primaryService) {
      this.updateOverallStatus(); // Renamed for clarity
    }

    // Emit service-specific state change event
    this.emit(`${service}_state_change`, { service, state: newState });
    // Emit general state change event
    this.emit('state_change', this.getState());
  }

  /**
   * Updates the reported status of the simulator.
   * @param status - The new simulator status string.
   */
  public updateSimulatorStatus(status: string): void {
    if (this.simulatorStatus !== status) {
      this.logger.info(`Simulator status changed: ${this.simulatorStatus} -> ${status}`);
      this.simulatorStatus = status;
      this.emit('simulator_status_change', { status });
      this.emit('state_change', this.getState());
    }
  }

  /**
   * Updates the connection recovery status.
   * @param isRecovering - Boolean indicating if recovery is in progress.
   * @param attempt - The current recovery attempt number (optional).
   */
  public updateRecovery(isRecovering: boolean, attempt: number = 0): void {
    const changed = this.isRecovering !== isRecovering || this.recoveryAttempt !== attempt;

    this.isRecovering = isRecovering;
    this.recoveryAttempt = attempt;

    if (changed) {
      this.logger.info(`Recovery state changed: isRecovering=${isRecovering}, attempt=${attempt}`);
      // Update overall status if recovery starts/stops
      this.updateOverallStatus();
      this.emit('recovery_change', { isRecovering, attempt });
      this.emit('state_change', this.getState());
    }
  }

  /**
   * Updates heartbeat information and calculates connection quality.
   * @param timestamp - The timestamp of the heartbeat event.
   * @param latency - The calculated latency for the heartbeat.
   */
  public updateHeartbeat(timestamp: number, latency: number): void {
    this.lastHeartbeatTime = timestamp;
    this.heartbeatLatency = latency;

    // Determine connection quality based on latency
    const newQuality = this.calculateConnectionQuality(latency);

    if (newQuality !== this.overallQuality) {
       this.logger.info(`Connection quality changed: ${this.overallQuality} -> ${newQuality} (Latency: ${latency}ms)`);
      this.overallQuality = newQuality;
      this.emit('quality_change', { quality: newQuality });
      this.emit('state_change', this.getState());
    }
  }

  // Calculate connection quality based on latency
  private calculateConnectionQuality(latency: number): ConnectionQuality {
    if (latency < 0) return ConnectionQuality.UNKNOWN; // Invalid latency
    if (latency <= 250) return ConnectionQuality.GOOD;
    if (latency <= 750) return ConnectionQuality.DEGRADED;
    return ConnectionQuality.POOR;
  }

  /**
   * Updates the overall connection status based on the primary service and recovery state.
   */
  private updateOverallStatus(): void {
    const primaryState = this.serviceStates.get(this.primaryService);
    if (!primaryState) {
        this.logger.error("Cannot update overall status: Primary service state not found.");
        return;
    }

    let newOverallStatus: ConnectionStatus;

    // If recovery is active, status is RECOVERING, regardless of primary service state
    if (this.isRecovering) {
        newOverallStatus = ConnectionStatus.RECOVERING;
    } else {
        // Otherwise, status matches the primary service's status
        newOverallStatus = primaryState.status;
    }


    if (newOverallStatus !== this.overallStatus) {
       this.logger.info(`Overall connection status changed: ${this.overallStatus} -> ${newOverallStatus}`);
      this.overallStatus = newOverallStatus;
      this.emit('status_change', { status: newOverallStatus });
      // General state change is emitted by the calling methods (updateServiceState, updateRecovery)
      // this.emit('state_change', this.getState()); // Avoid duplicate emission
    }
  }

  /**
   * Gets the current state of a specific service.
   * @param service - The type of service.
   * @returns The current ServiceState for the specified service.
   */
  public getServiceState(service: ConnectionServiceType): ServiceState {
    // Return a copy to prevent external modification
    const state = this.serviceStates.get(service);
    if (state) {
        return { ...state };
    }
    // Return a default disconnected state if not found (shouldn't happen with initialization)
    this.logger.error(`Requested state for uninitialized service: ${service}. Returning default.`);
    return {
      status: ConnectionStatus.DISCONNECTED,
      lastConnected: null,
      error: 'Service not initialized',
      recoveryAttempts: 0
    };
  }

  /**
   * Gets the complete, aggregated current connection state.
   * @returns An object representing the overall connection state.
   */
  public getState() {
    // Return a copy of the state object
    return {
      isConnected: this.overallStatus === ConnectionStatus.CONNECTED,
      isConnecting: this.overallStatus === ConnectionStatus.CONNECTING,
      isRecovering: this.isRecovering, // Use the dedicated flag
      recoveryAttempt: this.recoveryAttempt,
      connectionQuality: this.overallQuality,
      simulatorStatus: this.simulatorStatus,
      webSocketState: this.getServiceState(ConnectionServiceType.WEBSOCKET),
      sseState: this.getServiceState(ConnectionServiceType.SSE),
      // restState: this.getServiceState(ConnectionServiceType.REST), // If tracking REST health
      lastHeartbeatTime: this.lastHeartbeatTime,
      heartbeatLatency: this.heartbeatLatency,
      // Add overall status for clarity
      overallStatus: this.overallStatus
    };
  }

  /**
   * Resets all service states and overall status to disconnected/default values.
   */
  public reset(): void {
    this.logger.warn('Resetting all connection states.');
    this.serviceStates.forEach((_, service) => {
      // Reset each service individually, which triggers updateOverallStatus via primary service reset
      this.updateServiceState(service, {
        status: ConnectionStatus.DISCONNECTED,
        lastConnected: null,
        error: 'State reset', // Provide a reason
        recoveryAttempts: 0
      });
    });

    // Reset aggregated properties
    // this.overallStatus = ConnectionStatus.DISCONNECTED; // Handled by updateServiceState
    this.overallQuality = ConnectionQuality.UNKNOWN;
    this.isRecovering = false;
    this.recoveryAttempt = 0;
    this.lastHeartbeatTime = 0;
    this.heartbeatLatency = null;
    // simulatorStatus might persist across resets depending on requirements
    // this.simulatorStatus = 'UNKNOWN';

    // Emit final state change after reset
    this.emit('state_change', this.getState());
  }

   // Optional: Dispose method if needed (e.g., to clean up internal listeners if any)
   public dispose(): void {
       this.logger.warn('Disposing UnifiedConnectionState.');
       this.removeAllListeners();
   }
}
