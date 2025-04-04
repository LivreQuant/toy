// src/services/connection/connection-manager.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { ExchangeDataStream } from '../sse/exchange-data-stream';
import { HttpClient } from '../../api/http-client';
// Ensure this file exists and the path is correct
import { ConnectionRecoveryInterface } from './connection-recovery-interface';
import { RecoveryManager } from './recovery-manager';
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus,
  ServiceState // Ensure ServiceState is exported from unified-connection-state.ts
} from './unified-connection-state';
import { ConnectionDataHandlers } from './connection-data-handlers';
import { ConnectionSimulatorManager } from './connection-simulator';
import { Logger } from '../../utils/logger';
import { Disposable } from '../../utils/disposable';

/**
 * Orchestrates all client-side connections (WebSocket, SSE, REST via HttpClient)
 * and manages overall connection state, recovery, and data flow.
 */
export class ConnectionManager extends EventEmitter implements ConnectionRecoveryInterface, Disposable {
  private unifiedState: UnifiedConnectionState;
  private dataHandlers: ConnectionDataHandlers;
  private simulatorManager: ConnectionSimulatorManager;
  private recoveryManager: RecoveryManager;
  private wsManager: WebSocketManager;
  private sseManager: ExchangeDataStream;
  private tokenManager: TokenManager;
  private logger: Logger;
  private isDisposed: boolean = false;

  constructor(tokenManager: TokenManager, logger: Logger) {
    super();

    // Use the passed-in logger directly (removed createChild calls)
    this.logger = logger;
    this.logger.info('ConnectionManager Initializing...');

    this.tokenManager = tokenManager;

    // Create the unified state first, passing the logger
    this.unifiedState = new UnifiedConnectionState(this.logger);

    // Create HTTP client, passing only required args (assuming HttpClient constructor takes only tokenManager)
    const httpClient = new HttpClient(tokenManager /* removed logger */);

    // Create WebSocket manager, passing required args
    this.wsManager = new WebSocketManager(
        tokenManager,
        this.unifiedState,
        this.logger // Pass logger instance
        // Pass WS options if needed: {}
    );

    // Create SSE manager, passing required args
    // NOTE: Ensure ExchangeDataStream constructor matches these arguments.
    // It likely needs WebSocketManager OR relies solely on UnifiedConnectionState.
    // Assuming it needs TokenManager, UnifiedConnectionState, Logger for now.
    this.sseManager = new ExchangeDataStream(
        tokenManager,
        this.unifiedState, // Pass unified state
        this.logger // Pass logger instance
        // Pass SSE options if needed: {}
    );

    // Create data handlers, passing only required args
    this.dataHandlers = new ConnectionDataHandlers(httpClient /* removed logger */);

    // Create simulator manager, passing only required args
    this.simulatorManager = new ConnectionSimulatorManager(httpClient /* removed logger */);

    // Create recovery manager, passing required args
    this.recoveryManager = new RecoveryManager(
        this, // ConnectionRecoveryInterface implementation
        tokenManager,
        this.unifiedState
        // removed logger
    );

    this.setupEventListeners();
    this.logger.info('ConnectionManager Initialization Complete.');
  }

  private setupEventListeners(): void {
    this.logger.info('Setting up ConnectionManager event listeners...');
    // Forward unified state changes
    this.unifiedState.on('state_change', (state: any) => {
      if (this.isDisposed) return;
      this.emit('state_change', { current: state });
    });

    // Listen to WebSocket status from UnifiedState
    this.unifiedState.on('websocket_state_change', ({ state }: { state: ServiceState }) => {
        if (this.isDisposed) return;
        // Log significant changes
        if (state.status === ConnectionStatus.CONNECTED || state.status === ConnectionStatus.DISCONNECTED) {
            this.logger.info(`WebSocket state changed to: ${state.status}`, { error: state.error });
        }
        if (state.status === ConnectionStatus.CONNECTED) {
            this.emit('connected'); // Emit general connected event
        } else if (state.status === ConnectionStatus.DISCONNECTED) {
            this.emit('disconnected', { service: 'websocket', reason: state.error || 'disconnected' });
        }
    });

     // Listen to SSE status from UnifiedState
     this.unifiedState.on('sse_state_change', ({ state }: { state: ServiceState }) => {
         if (this.isDisposed) return;
         // Log significant changes
         if (state.status === ConnectionStatus.CONNECTED || state.status === ConnectionStatus.DISCONNECTED) {
            this.logger.info(`SSE state changed to: ${state.status}`, { error: state.error });
         }
         if (state.status === ConnectionStatus.DISCONNECTED && state.error) {
              this.emit('disconnected', { service: 'sse', reason: state.error });
         }
     });

    // Listen to specific data events from SSE Manager
    this.sseManager.on('exchange-data', (data: any) => {
      if (this.isDisposed) return;
      this.dataHandlers.updateExchangeData(data);
      this.emit('exchange_data', data);
    });

    this.sseManager.on('order-update', (data: any) => {
       if (this.isDisposed) return;
       this.logger.info('Received order update via SSE.');
       this.emit('order_update', data);
    });

    // Recovery events from RecoveryManager
    this.recoveryManager.on('recovery_attempt', (data: any) => {
      if (this.isDisposed) return;
      this.logger.warn('Connection recovery attempt started', data);
      this.emit('recovery_attempt', data);
    });
    this.recoveryManager.on('recovery_success', () => {
      if (this.isDisposed) return;
      this.logger.info('Connection recovery successful.');
      this.emit('recovery_success');
    });
    this.recoveryManager.on('recovery_failed', (data?: any) => { // Make data optional
      if (this.isDisposed) return;
      this.logger.error('Connection recovery failed.', data);
      this.emit('recovery_failed', data);
    });

    // Listen for token refresh events
    this.tokenManager.addRefreshListener(this.handleTokenRefresh);
    this.logger.info('ConnectionManager event listeners setup complete.');
  }

  // --- Lifecycle & State ---

  public dispose(): void {
    // ... (dispose implementation remains largely the same, ensure sub-manager dispose calls are correct) ...
     if (this.isDisposed) {
        this.logger.warn('ConnectionManager already disposed.');
        return;
    }
    this.logger.warn('Disposing ConnectionManager...');
    this.isDisposed = true;

    this.disconnect('manager_disposed'); // Ensure WS/SSE are closed

    // Clean up managers - check if they implement Disposable or have a dispose method
    if (this.recoveryManager && typeof (this.recoveryManager as any).dispose === 'function') {
       (this.recoveryManager as any).dispose();
    }
    // Use the Disposable type guard for wsManager and sseManager
    if (this.wsManager && typeof (this.wsManager as any)[Symbol.dispose] === 'function') {
       (this.wsManager as any)[Symbol.dispose]();
    } else if (this.wsManager && typeof (this.wsManager as any).dispose === 'function') {
         (this.wsManager as any).dispose();
    }
     if (this.sseManager && typeof (this.sseManager as any)[Symbol.dispose] === 'function') {
       (this.sseManager as any)[Symbol.dispose]();
    } else if (this.sseManager && typeof (this.sseManager as any).dispose === 'function') {
         (this.sseManager as any).dispose();
    }
    if (this.unifiedState && typeof (this.unifiedState as any).dispose === 'function') {
       (this.unifiedState as any).dispose();
    }

    if (this.tokenManager) {
      this.tokenManager.removeRefreshListener(this.handleTokenRefresh);
    }

    this.removeAllListeners();
    this.logger.warn('ConnectionManager disposed.');
  }

  public async connect(): Promise<boolean> {
     if (this.isDisposed) {
        this.logger.error("Cannot connect: ConnectionManager is disposed.");
        return false;
     }
    this.logger.info('Connection attempt requested via ConnectionManager.');
    // Connecting WebSocket will trigger SSE connection via state changes if successful
    return this.wsManager.connect();
  }

  public disconnect(reason: string = 'manual_disconnect'): void {
     if (this.isDisposed) return;
    this.logger.warn(`Disconnect requested via ConnectionManager. Reason: ${reason}`);
    // Disconnecting WebSocket should trigger SSE disconnect via state changes
    this.wsManager.disconnect(reason);
    // Explicitly disconnect SSE as well to be safe
    // *** FIX: Use disconnect() instead of close() ***
    this.sseManager.disconnect();
    this.logger.warn('Disconnect process completed via ConnectionManager.');
  }

  // Handles token refresh results
  private handleTokenRefresh = (success: boolean) => {
     if (this.isDisposed) return;
     this.logger.info(`Handling token refresh result in ConnectionManager: success = ${success}`);
    const isAuthenticated = success && this.tokenManager.isAuthenticated();
    // Update internal auth state for recovery manager
    this.updateRecoveryAuthState(isAuthenticated);

    if (!success) {
      this.logger.error('Authentication token refresh failed.');
      this.emit('auth_failed', 'Authentication token expired or refresh failed');
    }
  };

   // Private method to update recovery manager's auth state
   private updateRecoveryAuthState(isAuthenticated: boolean): void {
     if (this.isDisposed) return;
     this.logger.info(`Updating internal recovery auth state: isAuthenticated = ${isAuthenticated}`);
    if (!isAuthenticated) {
        this.logger.warn('Authentication lost, forcing disconnect.');
      this.disconnect('auth_lost'); // Force disconnect if auth is lost
    }
    // Notify recovery manager about auth state
    this.recoveryManager.updateAuthState(isAuthenticated);
  }


  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
     // ... (implementation remains the same) ...
      if (this.isDisposed) {
         this.logger.error("Cannot attempt recovery: ConnectionManager is disposed.");
         return false;
     }
    this.logger.warn(`Manual connection recovery attempt requested. Reason: ${reason}`);
    return this.recoveryManager.attemptRecovery(reason);
  }

  public getState() {
     // ... (implementation remains the same) ...
      if (this.isDisposed) {
         this.logger.warn("getState called on disposed ConnectionManager. Returning default state.");
         return new UnifiedConnectionState(this.logger).getState();
     }
    return this.unifiedState.getState();
  }

  // --- Data & Action Methods ---
  // ... (getExchangeData, submitOrder, cancelOrder, startSimulator, stopSimulator remain the same) ...
   public getExchangeData() {
     if (this.isDisposed) return {};
    return this.dataHandlers.getExchangeData();
  }

  public async submitOrder(order: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price?: number;
    type: 'MARKET' | 'LIMIT';
  }): Promise<{ success: boolean; orderId?: string; error?: string }> {
     if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    const state = this.getState();
    if (!state.isConnected) {
        this.logger.error('Submit order failed: Not connected.', { state });
      return { success: false, error: 'Not connected to trading servers' };
    }
    this.logger.info('Submitting order', { symbol: order.symbol, type: order.type, side: order.side });
    return this.dataHandlers.submitOrder(order);
  }

  public async cancelOrder(orderId: string): Promise<{ success: boolean; error?: string }> {
     if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    const state = this.getState();
    if (!state.isConnected) {
       this.logger.error('Cancel order failed: Not connected.', { state });
      return { success: false, error: 'Not connected to trading servers' };
    }
     this.logger.info('Cancelling order', { orderId });
    return this.dataHandlers.cancelOrder(orderId);
  }

  public async startSimulator(options: {
    initialSymbols?: string[],
    initialCash?: number
  } = {}): Promise<{ success: boolean; status?: string; error?: string }> {
     if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    const state = this.getState();
    if (!state.isConnected) {
        this.logger.error('Start simulator failed: Not connected.', { state });
      return { success: false, error: 'Not connected to trading servers' };
    }
     this.logger.info('Starting simulator', { options });
    return this.simulatorManager.startSimulator(options);
  }

  public async stopSimulator(): Promise<{ success: boolean; error?: string }> {
     if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    const state = this.getState();
    if (!state.isConnected) {
       this.logger.error('Stop simulator failed: Not connected.', { state });
      return { success: false, error: 'Not connected to trading servers' };
    }
     this.logger.info('Stopping simulator');
    return this.simulatorManager.stopSimulator();
  }


  // --- Reconnect Methods ---
  public async reconnect(): Promise<boolean> {
     // ... (implementation remains the same) ...
      if (this.isDisposed) {
         this.logger.error("Cannot reconnect: ConnectionManager is disposed.");
         return false;
     }
    this.logger.warn('Explicit reconnect requested.');
    return this.attemptRecovery('explicit_reconnect_request');
  }

  public async manualReconnect(): Promise<boolean> {
     // ... (implementation remains the same) ...
       if (this.isDisposed) {
         this.logger.error("Cannot manual reconnect: ConnectionManager is disposed.");
         return false;
     }
     this.logger.warn('Manual reconnect requested by user.');
    this.unifiedState.updateRecovery(true, 1);
    return this.attemptRecovery('manual_user_request');
  }

   // Implement [Symbol.dispose] for Disposable interface
   [Symbol.dispose](): void {
       this.dispose();
   }
}
