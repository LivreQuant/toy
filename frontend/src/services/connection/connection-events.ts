// src/services/connection/connection-events.ts
import { EventEmitter } from '../../utils/event-emitter';
import { 
  MarketData, 
  OrderUpdate, 
  PortfolioUpdate 
} from '../sse/exchange-data-stream';

export interface ConnectionEvents {
  // Lifecycle events
  connected: () => void;
  disconnected: () => void;
  reconnecting: (data: { attempt: number }) => void;

  // Data events
  market_data: (data: Record<string, MarketData>) => void;
  orders: (data: Record<string, OrderUpdate>) => void;
  portfolio: (data: PortfolioUpdate) => void;

  // Heartbeat events
  heartbeat: (data: { timestamp: number; latency: number }) => void;

  // Error events
  error: (error: string | Error) => void;

  // Simulator events
  simulator_update: (data: { 
    status: string; 
    simulatorId?: string 
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

  public emitMarketData(data: Record<string, MarketData>): void {
    this.emit('market_data', data);
  }

  public emitOrders(data: Record<string, OrderUpdate>): void {
    this.emit('orders', data);
  }

  public emitPortfolio(data: PortfolioUpdate): void {
    this.emit('portfolio', data);
  }

  public emitHeartbeat(timestamp: number, latency: number): void {
    this.emit('heartbeat', { timestamp, latency });
  }

  public emitError(error: string | Error): void {
    this.emit('error', error);
  }

  public emitSimulatorUpdate(status: string, simulatorId?: string): void {
    this.emit('simulator_update', { status, simulatorId });
  }
}