// src/services/websocket/types.ts

// Correct path assuming typed-event-emitter.ts moved to src/utils/
import { TypedEventEmitter } from '../../utils/typed-event-emitter';
import { TokenManager } from '../auth/token-manager';
// Correct path assuming device-id-manager.ts is in src/utils/
import { DeviceIdManager } from '../../utils/device-id-manager';
// Use EnhancedLogger consistently
import { EnhancedLogger } from '../../utils/enhanced-logger';
// Assuming WebSocketEvents definition might live elsewhere or be passed generically
// For now, using 'any' for the event map type if WebSocketEvents isn't defined here.
// Alternatively, import WebSocketEvents from './websocket-manager';

// Options for WebSocketManager constructor
export interface WebSocketOptions {
  heartbeatInterval?: number; // Interval for sending heartbeats (ms)
  heartbeatTimeout?: number;  // Timeout for receiving heartbeat response (ms)
  reconnectMaxAttempts?: number; // Max attempts (handled by ResilienceManager mainly)
  preventAutoConnect?: boolean;  // Should CM control connections? (Default: true)
}

// Dependencies for ConnectionStrategy (if you decide to use it separately)
export interface ConnectionStrategyDependencies {
  tokenManager: TokenManager;
  deviceIdManager: DeviceIdManager;
  eventEmitter: TypedEventEmitter<any>; // Use specific event map if available
  logger: EnhancedLogger;
  options?: WebSocketOptions;
}


// Dependencies for HeartbeatManager
export interface HeartbeatManagerOptions {
    interval?: number; // Interval for sending pings (ms)
    timeout?: number;  // Time to wait for pong response (ms)
}
export interface HeartbeatManagerDependencies {
  ws: WebSocket; // The WebSocket instance to manage
  // Use specific event emitter type if needed for HM communication
  eventEmitter: TypedEventEmitter<any>; // Or more specific type if HM emits events
  options?: HeartbeatManagerOptions;
}