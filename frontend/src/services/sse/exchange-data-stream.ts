// src/services/sse/exchange-data-stream.ts

import { SSEManager, SSEOptions } from './sse-manager'; // Import SSEOptions if needed
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { EventEmitter } from '../../utils/event-emitter';
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus
} from '../connection/unified-connection-state';
import { Logger } from '../../utils/logger'; // +++ ADDED: Import Logger +++
import { Disposable } from '../../utils/disposable'; // +++ ADDED: Import Disposable +++
import { ErrorHandler } from '../../utils/error-handler'; // Import

// Combine options for clarity
export interface ExchangeDataOptions extends SSEOptions { // Inherit SSE options
  // Add any ExchangeDataStream specific options here if needed
}

// +++ ADDED: Implement Disposable +++
export class ExchangeDataStream extends EventEmitter implements Disposable {
  private sseManager: SSEManager;
  private exchangeData: Record<string, any> = {};
  private tokenManager: TokenManager;
  private errorHandler: ErrorHandler; // Add if not already present

  // *** REMOVED: WebSocketManager instance variable (no longer directly needed) ***
  // private webSocketManager: WebSocketManager;
  private unifiedState: UnifiedConnectionState;
  private logger: Logger; // +++ ADDED: Logger instance variable +++
  private isDisposed: boolean = false; // +++ ADDED: Dispose flag +++

  constructor(
    tokenManager: TokenManager,
    // *** REMOVED: webSocketManager parameter ***
    // WebSocketManager is not directly used; coordination happens via UnifiedConnectionState
    unifiedState: UnifiedConnectionState,
    logger: Logger, // +++ ADDED: logger parameter +++
    errorHandler: ErrorHandler, // <-- Add parameter
    options: ExchangeDataOptions = {} // Accept combined options
  ) {
    super();

    this.errorHandler = errorHandler; // Store instance
    this.tokenManager = tokenManager;
    this.unifiedState = unifiedState;
    // +++ ADDED: Assign logger and create child logger +++
    this.logger = logger.createChild('ExchangeDataStream');
    this.logger.info('Initializing...');


    // +++ MODIFIED: Pass logger instance to SSEManager +++
    this.sseManager = new SSEManager(
        tokenManager,
        unifiedState,
        this.logger, // Pass the logger instance down
        this.errorHandler, // <-- Pass instance here
        options // Pass options (includes SSE options like reconnect attempts, circuit breaker settings)
    );

    this.setupListeners();
    this.logger.info('Initialized.');
  }

  /**
   * Sets up listeners for events emitted by the underlying SSEManager.
   */
  private setupListeners(): void {
      this.logger.info('Setting up SSEManager event listeners...');
      // Forward relevant SSE events
      this.sseManager.on('connected', (data: any) => { if (!this.isDisposed) this.emit('connected', data); });
      this.sseManager.on('disconnected', (data: any) => { if (!this.isDisposed) this.emit('disconnected', data); });
      this.sseManager.on('reconnecting', (data: any) => { if (!this.isDisposed) this.emit('reconnecting', data); });
      this.sseManager.on('error', this.handleError.bind(this)); // Handle errors locally first
      this.sseManager.on('circuit_open', (data: any) => { if (!this.isDisposed) this.emit('circuit_open', data); });
      this.sseManager.on('circuit_closed', (data: any) => { if (!this.isDisposed) this.emit('circuit_closed', data); });

      // Listen specifically for data events to update internal cache and re-emit
      this.sseManager.on('exchange-data', this.handleExchangeData.bind(this));
      this.sseManager.on('order-update', this.handleOrderUpdate.bind(this)); // Example specific event
      // Add listeners for other specific data events emitted by SSEManager
  }

  /**
   * Checks if the SSE stream is currently connected.
   * Relies on the UnifiedConnectionState.
   * @returns True if connected, false otherwise.
   */
  public isConnected(): boolean {
    // Check SSE connection status via UnifiedState
    const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
    return sseState.status === ConnectionStatus.CONNECTED;
  }

  /**
   * Attempts to connect the SSE stream.
   * This will typically only succeed if the primary WebSocket connection is active.
   * The underlying SSEManager handles the actual connection logic and state updates.
   * @returns A promise resolving to true if the connection attempt was successful, false otherwise.
   */
  public async connect(): Promise<boolean> {
    if (this.isDisposed) {
        this.logger.error("Cannot connect: ExchangeDataStream is disposed.");
        return false;
    }
    this.logger.info('Connect requested.');
    // Delegate connection attempt to SSEManager
    // SSEManager internally checks WebSocket status via UnifiedConnectionState before proceeding
    return this.sseManager.connect();
  }

  /**
   * Gets the current status details of the SSE connection.
   * @returns An object containing connection status details.
   */
  public getConnectionStatus(): {
    status: ConnectionStatus;
    error: string | null;
    circuitBreakerState: ReturnType<SSEManager['getConnectionStatus']>['circuitBreakerState']; // Get type from SSEManager
    reconnectAttempt: number;
  } {
    const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
    const sseManagerStatus = this.sseManager.getConnectionStatus(); // Get detailed status from manager

    return {
      status: sseState.status,
      error: sseState.error,
      circuitBreakerState: sseManagerStatus.circuitBreakerState,
      reconnectAttempt: sseState.recoveryAttempts // Get attempts from unified state
    };
  }

  /**
   * Handles incoming 'exchange-data' events from SSEManager.
   * Updates the internal cache and re-emits the data.
   * @param data - The exchange data received.
   */
  private handleExchangeData(data: any): void {
    if (this.isDisposed) return;
    try {
      // Optional: Add validation or transformation logic here
      this.exchangeData = { ...this.exchangeData, ...data }; // Merge data
      this.emit('exchange-data', data); // Emit the raw event data
    } catch (error) {
      this.logger.error('Error processing exchange data:', { error, rawData: data });
      this.handleError({ error: 'Error processing exchange data', originalError: error });
    }
  }

   /**
   * Handles incoming 'order-update' events from SSEManager (example).
   * Re-emits the data.
   * @param data - The order update data received.
   */
  private handleOrderUpdate(data: any): void {
    if (this.isDisposed) return;
    try {
      // Optional: Add validation or transformation logic here
      this.emit('order-update', data);
    } catch (error) {
      this.logger.error('Error processing order update:', { error, rawData: data });
      this.handleError({ error: 'Error processing order update', originalError: error });
    }
  }


  /**
   * Disconnects the SSE stream by closing the underlying SSEManager connection.
   */
  public disconnect(): void {
    if (this.isDisposed) return;
    this.logger.info('Disconnect requested.');
    // Delegate closing to SSEManager
    this.sseManager.close();
  }

  /**
   * Retrieves a copy of the latest cached exchange data.
   * @returns A copy of the exchange data object.
   */
  public getExchangeData(): Record<string, any> {
    // Return a copy to prevent external modification
    return { ...this.exchangeData };
  }

  /**
   * Handles 'error' events from the underlying SSEManager.
   * Logs the error and re-emits it.
   * @param error - The error object or details received.
   */
  private handleError(error: any): void {
    if (this.isDisposed) return;
    this.logger.error('SSE stream error:', error);
    // Re-emit the error for the ConnectionManager or other listeners
    this.emit('error', error);
  }

  /**
   * Disposes of the ExchangeDataStream, cleaning up resources and listeners.
   */
  public dispose(): void {
    if (this.isDisposed) return;
    this.logger.warn('Disposing ExchangeDataStream...');
    this.isDisposed = true;
    this.disconnect(); // Ensure SSEManager is closed

    // Dispose SSEManager if it has a dispose method
    if (this.sseManager && typeof (this.sseManager as any).dispose === 'function') {
        (this.sseManager as any).dispose();
    }

    this.removeAllListeners(); // Clean up own listeners
    this.logger.warn('ExchangeDataStream disposed.');
  }

  /**
   * Implements the [Symbol.dispose] method for the Disposable interface.
   */
  [Symbol.dispose](): void {
      this.dispose();
  }
}
