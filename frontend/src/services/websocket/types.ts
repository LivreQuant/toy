import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';

export interface WebSocketOptions {
  heartbeatInterval?: number;
  heartbeatTimeout?: number;
  reconnectMaxAttempts?: number;
}

export interface ConnectionStrategyDependencies {
  tokenManager: TokenManager;
  eventEmitter: EventEmitter;
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
  isMaster: boolean;
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