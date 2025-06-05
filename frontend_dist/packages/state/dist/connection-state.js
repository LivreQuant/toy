// src/connection-state.ts
import { BaseStateService } from './base-state-service';
// Define enums for connection status
export var ConnectionStatus;
(function (ConnectionStatus) {
    ConnectionStatus["DISCONNECTED"] = "disconnected";
    ConnectionStatus["CONNECTING"] = "connecting";
    ConnectionStatus["CONNECTED"] = "connected";
    ConnectionStatus["RECOVERING"] = "recovering";
})(ConnectionStatus || (ConnectionStatus = {}));
export var ConnectionQuality;
(function (ConnectionQuality) {
    ConnectionQuality["GOOD"] = "good";
    ConnectionQuality["DEGRADED"] = "degraded";
    ConnectionQuality["POOR"] = "poor";
    ConnectionQuality["UNKNOWN"] = "unknown";
})(ConnectionQuality || (ConnectionQuality = {}));
// Initial connection state
export const initialConnectionState = {
    overallStatus: ConnectionStatus.DISCONNECTED,
    webSocketStatus: ConnectionStatus.DISCONNECTED,
    quality: ConnectionQuality.UNKNOWN,
    isRecovering: false,
    recoveryAttempt: 0,
    simulatorStatus: 'UNKNOWN',
    lastConnectionError: null,
};
// Connection state service
export class ConnectionStateService extends BaseStateService {
    constructor() {
        super(initialConnectionState);
    }
    // Override updateState to handle overall status calculation
    updateState(changes) {
        var _a, _b, _c;
        const currentState = this.getState();
        // Recalculate overall status if specific statuses change
        let newOverallStatus = (_a = changes.overallStatus) !== null && _a !== void 0 ? _a : currentState.overallStatus;
        if (changes.webSocketStatus || changes.isRecovering !== undefined) {
            const wsStatus = (_b = changes.webSocketStatus) !== null && _b !== void 0 ? _b : currentState.webSocketStatus;
            const isRecovering = (_c = changes.isRecovering) !== null && _c !== void 0 ? _c : currentState.isRecovering;
            if (isRecovering) {
                newOverallStatus = ConnectionStatus.RECOVERING;
            }
            else {
                newOverallStatus = wsStatus;
            }
        }
        // Update the state with computed overall status
        const newState = Object.assign(Object.assign(Object.assign({}, currentState), changes), { overallStatus: newOverallStatus });
        this.logger.debug('Updating connection state', {
            changes,
            newOverallStatus,
            currentOverallStatus: currentState.overallStatus
        });
        this.state$.next(newState);
    }
    // Calculate connection quality based on latency
    calculateConnectionQuality(latency) {
        if (latency === null || latency < 0)
            return ConnectionQuality.UNKNOWN;
        if (latency <= 250)
            return ConnectionQuality.GOOD;
        if (latency <= 750)
            return ConnectionQuality.DEGRADED;
        return ConnectionQuality.POOR;
    }
    // Reset to initial state
    reset() {
        this.setState(initialConnectionState);
    }
}
// Export singleton instance
export const connectionState = new ConnectionStateService();
