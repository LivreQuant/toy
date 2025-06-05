// src/types/connection-types.ts
import { ConnectionStatus } from '@trading-app/state';

export interface ConnectionDesiredState {
  connected: boolean;
  simulatorRunning: boolean;
}

export interface ConnectionManagerOptions {
  heartbeatInterval?: number;
  heartbeatTimeout?: number;
  resilience?: {
    initialDelayMs?: number;
    maxDelayMs?: number;
    maxAttempts?: number;
    suspensionTimeoutMs?: number;
    failureThreshold?: number;
    jitterFactor?: number;
  };
}

export interface SocketClientOptions {
  autoReconnect?: boolean;
  connectTimeout?: number;
  secureConnection?: boolean;
}

export interface HeartbeatOptions {
  interval: number;
  timeout: number;
}

export interface ResilienceOptions {
  initialDelayMs?: number;
  maxDelayMs?: number;
  maxAttempts?: number;
  suspensionTimeoutMs?: number;
  failureThreshold?: number;
  jitterFactor?: number;
}

// Dependency injection interfaces
export interface ToastService {
  info(message: string, duration?: number, id?: string): void;
  warning(message: string, duration?: number, id?: string): void;
  error(message: string, duration?: number, id?: string): void;
  success(message: string, duration?: number, id?: string): void;
}

export interface StateManager {
  updateConnectionState(changes: any): void;
  updateSimulatorState(changes: any): void;
  updateExchangeState(changes: any): void;
  updatePortfolioState(changes: any): void;
  getConnectionState(): any;
  getAuthState(): any;
}

export interface ConfigService {
  getWebSocketUrl(): string;
  getReconnectionConfig(): {
    initialDelayMs: number;
    maxDelayMs: number;
    jitterFactor: number;
    maxAttempts: number;
  };
}