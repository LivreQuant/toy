// src/services/connection/connection-events.ts
import { EventEmitter } from '../../utils/event-emitter';

export interface ConnectionEvents {
  // Lifecycle events
  connected: () => void;
  disconnected: () => void;
  reconnecting: (data: { attempt: number }) => void;

  // Data events
  exchange_data: (data: any) => void; // Changed from market_data
  orders: (data: Record<string, any>) => void;
  portfolio: (data: any) => void;

  // Heartbeat events
  heartbeat: (data: { timestamp: number; latency: number }) => void;

  // Error events
  error: (error: string | Error) => void;

  // Simulator events
  simulator_update: (data: { 
    status: string; 
  }) => void;
}

export class ConnectionEventManager extends EventEmitter {
  public emitConnected(): void {
    this.emit('connected');
  }

  public emitDisconnected(): void {
    this.emit('disconnected');
  }

  public emitReconnecting(attempt: number): void {
    this.emit('reconnecting', { attempt });
  }

  public emitExchangeData(data: any): void { // Changed from emitMarketData
    this.emit('exchange_data', data);
  }

  public emitOrders(data: Record<string, any>): void {
    this.emit('orders', data);
  }

  public emitHeartbeat(timestamp: number, latency: number): void {
    this.emit('heartbeat', { timestamp, latency });
  }

  public emitError(error: string | Error): void {
    this.emit('error', error);
  }

  public emitSimulatorUpdate(status: string): void {
    this.emit('simulator_update', { status });
  }
}