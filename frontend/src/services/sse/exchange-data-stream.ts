// src/services/sse/exchange-data-stream.ts

import { SSEManager, SSEOptions } from './sse-manager';
// <<< FIX: Import CircuitState from its actual source file >>>
import { CircuitState } from '../../utils/circuit-breaker';
import { TokenManager } from '../auth/token-manager';
// WebSocketManager import likely not needed if instance isn't stored
// import { WebSocketManager } from '../websocket/websocket-manager';
import { EventEmitter } from '../../utils/event-emitter';
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus
} from '../connection/unified-connection-state';
import { Logger } from '../../utils/logger';
import { Disposable } from '../../utils/disposable';
import { ErrorHandler } from '../../utils/error-handler';

// Update the ExchangeDataOptions interface to include preventAutoConnect property
export interface ExchangeDataOptions extends SSEOptions {
  // Add any ExchangeDataStream specific options here if needed
  preventAutoConnect?: boolean; // Add this new option
}

export class ExchangeDataStream extends EventEmitter implements Disposable {
  private sseManager: SSEManager;
  private exchangeData: Record<string, any> = {};
  private tokenManager: TokenManager;
  private errorHandler: ErrorHandler;
  private unifiedState: UnifiedConnectionState;
  private logger: Logger;
  private isDisposed: boolean = false;

  constructor(
    tokenManager: TokenManager,
    unifiedState: UnifiedConnectionState,
    logger: Logger,
    errorHandler: ErrorHandler,
    options: ExchangeDataOptions = {}
  ) {
    super();

    this.errorHandler = errorHandler;
    this.tokenManager = tokenManager;
    this.unifiedState = unifiedState;
    this.logger = logger.createChild('ExchangeDataStream');
    this.logger.info('Initializing...');

    // Pass preventAutoConnect to SSEManager
    this.sseManager = new SSEManager(
      tokenManager,
      unifiedState,
      this.logger,
      this.errorHandler,
      {
        ...options,
        preventAutoConnect: options.preventAutoConnect // Pass it through
      }
    );

    this.setupListeners();
    this.logger.info('Initialized.');
  }

  private setupListeners(): void {
      this.logger.info('Setting up SSEManager event listeners...');
      // Forward relevant SSE events
      this.sseManager.on('connected', (data: any) => { if (!this.isDisposed) this.emit('connected', data); });
      this.sseManager.on('disconnected', (data: any) => { if (!this.isDisposed) this.emit('disconnected', data); });
      this.sseManager.on('reconnecting', (data: any) => { if (!this.isDisposed) this.emit('reconnecting', data); });
      this.sseManager.on('error', this.handleError.bind(this));
      this.sseManager.on('circuit_open', (data: any) => { if (!this.isDisposed) this.emit('circuit_open', data); });
      this.sseManager.on('circuit_closed', (data: any) => { if (!this.isDisposed) this.emit('circuit_closed', data); });
      this.sseManager.on('connection_lost_permanently', (data: any) => { if (!this.isDisposed) this.emit('connection_lost_permanently', data); }); // Forward if needed
      this.sseManager.on('max_reconnect_attempts', (data: any) => { if (!this.isDisposed) this.emit('max_reconnect_attempts', data); }); // Forward if needed


      // Listen specifically for data events
      this.sseManager.on('exchange-data', this.handleExchangeData.bind(this));
      this.sseManager.on('order-update', this.handleOrderUpdate.bind(this));
      this.sseManager.on('message', (msg: { type: string, data: any }) => { // Example generic message listener
          if (!this.isDisposed) this.emit('message', msg);
      });
  }

  public isConnected(): boolean {
    if (this.isDisposed) return false;
    const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
    return sseState.status === ConnectionStatus.CONNECTED;
  }

  public async connect(): Promise<boolean> {
    if (this.isDisposed) {
        this.logger.error("Cannot connect: ExchangeDataStream is disposed.");
        return false;
    }
    this.logger.info('Connect requested.');
    return this.sseManager.connect();
  }

   public getConnectionStatus(): ReturnType<SSEManager['getConnectionStatus']> {
    if (this.isDisposed) {
       return {
           connected: false, connecting: false,
           circuitBreakerState: CircuitState.CLOSED, // Default state
           reconnectAttempt: 0,
           maxReconnectAttempts: this.sseManager?.getConnectionStatus()?.maxReconnectAttempts ?? 0,
       };
    }
    return this.sseManager.getConnectionStatus();
  }


  private handleExchangeData(data: any): void {
    if (this.isDisposed) return;
    try {
      // Simple merge, consider more sophisticated update logic if needed
      this.exchangeData = { ...this.exchangeData, ...data };
      this.emit('exchange-data', data);
    } catch (error) {
      this.logger.error('Error processing exchange data:', { error, rawData: data });
      this.handleError({ error: 'Error processing exchange data', originalError: error });
    }
  }

  private handleOrderUpdate(data: any): void {
    if (this.isDisposed) return;
    try {
      this.emit('order-update', data);
    } catch (error) {
      this.logger.error('Error processing order update:', { error, rawData: data });
      this.handleError({ error: 'Error processing order update', originalError: error });
    }
  }


  /**
   * Disconnects the SSE stream by closing the underlying SSEManager connection.
   * <<< MODIFIED to accept optional reason >>>
   * @param reason - Optional reason for disconnection.
   */
  public disconnect(reason?: string): void { // <<< Added reason?: string
    if (this.isDisposed) return;
    this.logger.info(`Disconnect requested. Reason: ${reason ?? 'N/A'}`);
    // Delegate closing to SSEManager, passing the reason
    this.sseManager.close(reason); // <<< Pass reason
  }

  public getExchangeData(): Record<string, any> {
    if (this.isDisposed) return {};
    // Return a copy to prevent external modification
    return { ...this.exchangeData };
  }

  private handleError(error: any): void {
    if (this.isDisposed) return;
    this.logger.error('SSE stream error:', error);
    // Re-emit the error for the ConnectionManager or other listeners
    this.emit('error', error);
  }

  public dispose(): void {
    if (this.isDisposed) return;
    this.logger.warn('Disposing ExchangeDataStream...');
    this.isDisposed = true;
    this.disconnect('dispose'); // Ensure SSEManager is closed with reason

    // Dispose SSEManager
    if (this.sseManager && typeof (this.sseManager as any)[Symbol.dispose] === 'function') {
        (this.sseManager as any)[Symbol.dispose]();
    } else if (this.sseManager && typeof (this.sseManager as any).dispose === 'function') {
         (this.sseManager as any).dispose();
    }

    this.removeAllListeners();
    this.logger.warn('ExchangeDataStream disposed.');
  }

  [Symbol.dispose](): void {
      this.dispose();
  }
}