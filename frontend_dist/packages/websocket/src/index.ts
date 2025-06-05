// src/index.ts
export * from './types';
export * from './client';
export * from './handlers';
export * from './services';
export * from './utils';

// Export key classes for easy access
export { ConnectionManager } from './client/connection-manager';
export { SocketClient } from './client/socket-client';
export { SessionHandler } from './handlers/session-handler';
export { SimulatorHandler } from './handlers/simulator-handler';
export { ExchangeDataHandler } from './handlers/exchange-data-handler';
export { Heartbeat } from './services/heartbeat';
export { Resilience, ResilienceState } from './services/resilience';
export { SimulatorClient } from './services/simulator-client';

// Export factory function for easy setup
export { createConnectionManagerWithGlobalDeps } from './utils/connection-utils';