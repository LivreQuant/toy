// src/services/websocket/websocket-event-types.ts
import { ConnectionStatus, ConnectionQuality } from '../connection/unified-connection-state';

export interface WebSocketEvents {
  connected: void;
  disconnected: { code?: number; reason?: string; wasClean?: boolean };
  message: any;
  heartbeat: {
    timestamp: number;
    latency: number;
    simulatorStatus?: string;
    deviceId?: string;
  };
  message_error: {
    error: Error;
    rawData: any;
  };
  exchange_data: Record<string, any>;
  portfolio_data: {
    positions: Record<string, any>;
    cash: number;
    timestamp: number;
  };
  order_update: {
    orderId: string;
    status: string;
    filledQty: number;
    remainingQty: number;
    timestamp: number;
  };
  state_change: {
    current: {
      isConnected: boolean;
      isConnecting: boolean;
      isRecovering: boolean;
      recoveryAttempt: number;
      connectionQuality: ConnectionQuality;
      simulatorStatus: string;
      overallStatus: ConnectionStatus;
    }
  };
}