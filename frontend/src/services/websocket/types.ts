import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';

import { DeviceIdManager } from '../../utils/device-id-manager'; // Import
import { Logger } from '../../utils/logger'; // Import

export interface WebSocketOptions {
  heartbeatInterval?: number;
  heartbeatTimeout?: number;
  reconnectMaxAttempts?: number;
  preventAutoConnect?: boolean; // Add this new option
}

export interface ConnectionStrategyDependencies {
  tokenManager: TokenManager;
  deviceIdManager: DeviceIdManager; // <-- Add this
  eventEmitter: EventEmitter;
  logger: Logger; // <-- Add this
  options?: WebSocketOptions;
}

export enum ConnectionQuality {
  EXCELLENT = 'excellent',
  GOOD = 'good',
  FAIR = 'fair',
  POOR = 'poor',
  DISCONNECTED = 'disconnected'
}

export interface ConnectionMetrics {
  latency: number;
  bandwidth: number;
  packetLoss: number;
}

export interface DataSourceConfig {
  type: 'websocket' | 'sse' | 'rest';
  url: string;
  priority: number;
}

export interface HeartbeatData {
  timestamp: number;
  simulatorStatus: string;
  deviceId: string;
}

export interface HeartbeatManagerDependencies {
  ws: WebSocket;
  eventEmitter: EventEmitter;
  options?: {
    interval?: number;
    timeout?: number;
  };
}