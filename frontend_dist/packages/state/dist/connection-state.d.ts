import { BaseStateService } from './base-state-service';
export declare enum ConnectionStatus {
    DISCONNECTED = "disconnected",
    CONNECTING = "connecting",
    CONNECTED = "connected",
    RECOVERING = "recovering"
}
export declare enum ConnectionQuality {
    GOOD = "good",
    DEGRADED = "degraded",
    POOR = "poor",
    UNKNOWN = "unknown"
}
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
export declare const initialConnectionState: ConnectionState;
export declare class ConnectionStateService extends BaseStateService<ConnectionState> {
    constructor();
    updateState(changes: Partial<ConnectionState>): void;
    calculateConnectionQuality(latency: number | null): ConnectionQuality;
    reset(): void;
}
export declare const connectionState: ConnectionStateService;
