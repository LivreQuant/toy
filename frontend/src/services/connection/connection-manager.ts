// src/services/connection/connection-manager.ts
import { EventEmitter } from '../../utils/event-emitter';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { ExchangeDataStream } from '../sse/exchange-data-stream';
// import { SessionApi } from '../../api/session'; // SessionApi seems unused directly here now
import { HttpClient } from '../../api/http-client';
import { ConnectionRecoveryInterface } from './connection-recovery-interface';
import { RecoveryManager } from './recovery-manager';
import {
  UnifiedConnectionState,
  ConnectionServiceType,
  ConnectionStatus
} from './unified-connection-state';
import { ConnectionDataHandlers } from './connection-data-handlers';
import { ConnectionSimulatorManager } from './connection-simulator';
import { Logger } from '../../utils/logger'; // Import Logger
import { Disposable } from '../../utils/disposable'; // Ensure Disposable is imported if needed

export class ConnectionManager extends EventEmitter implements ConnectionRecoveryInterface, Disposable {
  private unifiedState: UnifiedConnectionState;
  private dataHandlers: ConnectionDataHandlers;
  private simulatorManager: ConnectionSimulatorManager;
  private recoveryManager: RecoveryManager;
  private wsManager: WebSocketManager;
  private sseManager: ExchangeDataStream;
  private tokenManager: TokenManager;
  private logger: Logger; // Add logger instance
  private isDisposed: boolean = false; // Track disposal state

  constructor(tokenManager: TokenManager, logger: Logger) { // Inject Logger
    super();

    this.logger = logger.createChild('ConnectionManager'); // Create a child logger for context
    this.logger.info('Initializing...');

    this.tokenManager = tokenManager;

    // Create the unified state first
    this.unifiedState = new UnifiedConnectionState(this.logger.createChild('UnifiedState'));

    // Create HTTP client
    const httpClient = new HttpClient(tokenManager, this.logger.createChild('HttpClient'));

    // Create WebSocket manager with unified state & logger
    this.wsManager = new WebSocketManager(
        tokenManager,
        this.unifiedState,
        this.logger.createChild('WebSocketManager')
        // Pass WS options if needed: {}
    );

    // Create SSE manager with unified state, WebSocket reference (implicitly via unifiedState now), & logger
    this.sseManager = new ExchangeDataStream(
        tokenManager,
        // this.wsManager, // Direct WS Manager reference might not be needed if coordination happens via UnifiedState
        this.unifiedState,
        this.logger.createChild('ExchangeDataStream')
        // Pass SSE options if needed: {}
    );

    // Create data handlers
    this.dataHandlers = new ConnectionDataHandlers(httpClient, this.logger.createChild('DataHandlers'));

    // Create simulator manager
    this.simulatorManager = new ConnectionSimulatorManager(httpClient, this.logger.createChild('SimulatorManager'));

    // Create recovery manager with unified state
    this.recoveryManager = new RecoveryManager(
        this,
        tokenManager,
        this.unifiedState,
        this.logger.createChild('RecoveryManager')
    );

    this.setupEventListeners();
    this.logger.info('Initialization Complete.');
  }

  private setupEventListeners(): void {
    this.logger.info('Setting up event listeners...');
    // Forward unified state changes
    this.unifiedState.on('state_change', (state: any) => {
      if (this.isDisposed) return;
      // Avoid logging every state change unless debugging, can be noisy
      // this.logger.info('Unified state changed', state);
      this.emit('state_change', { current: state });
    });

    // Listen to WebSocket status from UnifiedState instead of directly
    this.unifiedState.on('websocket_state_change', ({ state }: { state: ServiceState }) => {
        if (this.isDisposed) return;
        this.logger.info(`WebSocket state changed to: ${state.status}`, { error: state.error });
        if (state.status === ConnectionStatus.CONNECTED) {
            this.emit('connected'); // Emit general connected event
             // SSE connection is handled automatically by SSEManager listening to WS state changes
             // No need to explicitly call connectSSE here.
        } else if (state.status === ConnectionStatus.DISCONNECTED) {
            this.emit('disconnected', { service: 'websocket', reason: state.error || 'disconnected' });
        }
    });

     // Listen to SSE status from UnifiedState
     this.unifiedState.on('sse_state_change', ({ state }: { state: ServiceState }) => {
         if (this.isDisposed) return;
         this.logger.info(`SSE state changed to: ${state.status}`, { error: state.error });
         if (state.status === ConnectionStatus.DISCONNECTED && state.error) {
              this.emit('disconnected', { service: 'sse', reason: state.error });
         }
     });


    // Listen to specific data events from SSE Manager
    this.sseManager.on('exchange-data', (data: any) => {
      if (this.isDisposed) return;
      // Avoid logging potentially large data structures frequently
      // this.logger.info('Received exchange data');
      this.dataHandlers.updateExchangeData(data); // Update internal cache if needed
      this.emit('exchange_data', data); // Forward event
    });

     // Example: Listen for order updates from SSE Manager if applicable
    this.sseManager.on('order-update', (data: any) => {
       if (this.isDisposed) return;
       this.logger.info('Received order update');
       // Handle order update, maybe update local state or emit
       this.emit('order_update', data);
    });


    // Recovery events from RecoveryManager
    this.recoveryManager.on('recovery_attempt', (data: any) => {
      if (this.isDisposed) return;
      this.logger.warn('Connection recovery attempt', data);
      this.emit('recovery_attempt', data);
    });

    this.recoveryManager.on('recovery_success', () => {
      if (this.isDisposed) return;
      this.logger.info('Connection recovery successful.');
      this.emit('recovery_success');
    });

    this.recoveryManager.on('recovery_failed', (data: any) => { // Pass data if available
      if (this.isDisposed) return;
      this.logger.error('Connection recovery failed.', data);
      this.emit('recovery_failed', data);
    });

    // Listen for token refresh events to update auth state
    this.tokenManager.addRefreshListener(this.handleTokenRefresh);
    this.logger.info('Event listeners setup complete.');
  }


  public dispose(): void {
    if (this.isDisposed) {
        this.logger.warn('ConnectionManager already disposed.');
        return;
    }
    this.logger.warn('Disposing ConnectionManager...');
    this.isDisposed = true;

    // Disconnect services first
    this.disconnect(); // Ensure WS/SSE are closed

    // Clean up managers that implement Disposable
    if (this.recoveryManager && typeof (this.recoveryManager as any).dispose === 'function') {
       (this.recoveryManager as any).dispose();
    }
    if (this.wsManager && typeof (this.wsManager as any).dispose === 'function') {
       (this.wsManager as any).dispose();
    }
    if (this.sseManager && typeof (this.sseManager as any).dispose === 'function') {
       (this.sseManager as any).dispose();
    }
    if (this.unifiedState && typeof (this.unifiedState as any).dispose === 'function') {
       (this.unifiedState as any).dispose(); // Dispose unified state if it has resources
    }
    // Dispose other managers if they implement Disposable

    // Clean up auth state monitoring
    if (this.tokenManager) {
      this.tokenManager.removeRefreshListener(this.handleTokenRefresh);
    }

    // Remove all event listeners managed by this instance
    this.removeAllListeners(); // From EventEmitter base class
    this.logger.warn('ConnectionManager disposed.');
  }

  // Removed connectSSE as it's handled by SSEManager reacting to UnifiedState

  // Lifecycle Methods - WebSocket is the primary connection trigger
  public async connect(): Promise<boolean> {
     if (this.isDisposed) {
        this.logger.error("Cannot connect: ConnectionManager is disposed.");
        return false;
     }
    this.logger.info('Connection attempt requested.');
    // Connecting WebSocket will trigger SSE connection via state changes if successful
    return this.wsManager.connect();
  }

  public disconnect(reason: string = 'manual_disconnect'): void {
     if (this.isDisposed) return;
    this.logger.warn(`Disconnect requested. Reason: ${reason}`);
    // Disconnecting WebSocket should trigger SSE disconnect via state changes
    this.wsManager.disconnect(reason);
    // Explicitly close SSE as well to be safe, though it should react to WS disconnect
    this.sseManager.close();
    // Resetting unified state might be too aggressive here, let individual managers handle state updates
    // this.unifiedState.reset();
    this.logger.warn('Disconnect process completed.');
  }

  // Method to update recovery auth state (called by token refresh handler)
  private updateRecoveryAuthState(isAuthenticated: boolean): void {
     if (this.isDisposed) return;
     this.logger.info(`Updating recovery auth state: isAuthenticated = ${isAuthenticated}`);
    if (!isAuthenticated) {
        this.logger.warn('Authentication lost, forcing disconnect.');
      this.disconnect('auth_lost'); // Force disconnect if auth is lost
    }
    // Notify recovery manager about auth state
    this.recoveryManager.updateAuthState(isAuthenticated);
  }

  private handleTokenRefresh = (success: boolean) => {
     if (this.isDisposed) return;
     this.logger.info(`Handling token refresh result: success = ${success}`);
    // Check authentication status *after* refresh attempt
    const isAuthenticated = success && this.tokenManager.isAuthenticated();
    this.updateRecoveryAuthState(isAuthenticated);

    if (!success) {
      this.logger.error('Authentication token refresh failed.');
      this.emit('auth_failed', 'Authentication token expired or refresh failed');
      // Disconnect is handled within updateRecoveryAuthState(false)
    }
  };

  public async attemptRecovery(reason: string = 'manual'): Promise<boolean> {
     if (this.isDisposed) {
         this.logger.error("Cannot attempt recovery: ConnectionManager is disposed.");
         return false;
     }
    this.logger.warn(`Manual connection recovery attempt requested. Reason: ${reason}`);
    return this.recoveryManager.attemptRecovery(reason);
  }

  public getState() {
     if (this.isDisposed) {
         this.logger.warn("getState called on disposed ConnectionManager. Returning default state.");
         // Return a default/disconnected state instead of null or throwing error
         return new UnifiedConnectionState(this.logger).getState(); // Or a predefined static disconnected state
     }
    return this.unifiedState.getState();
  }

  // --- Data & Action Methods ---

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
    // Check overall connected status from unified state
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

  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
     if (this.isDisposed) return { success: false, error: 'Connection manager disposed' };
    const state = this.getState();
    if (!state.isConnected) {
        this.logger.error('Start simulator failed: Not connected.', { state });
      return { success: false, error: 'Not connected to trading servers' };
    }
     this.logger.info('Starting simulator');
    return this.simulatorManager.startSimulator();
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

  // Explicit reconnect method - uses recovery manager for consistency
  public async reconnect(): Promise<boolean> {
     if (this.isDisposed) {
         this.logger.error("Cannot reconnect: ConnectionManager is disposed.");
         return false;
     }
    this.logger.warn('Explicit reconnect requested.');
    // Use the recovery mechanism for a controlled reconnect
    return this.attemptRecovery('explicit_reconnect_request');
  }

  // Manual reconnect method (user-initiated) - uses recovery manager
  public async manualReconnect(): Promise<boolean> {
      if (this.isDisposed) {
         this.logger.error("Cannot manual reconnect: ConnectionManager is disposed.");
         return false;
     }
     this.logger.warn('Manual reconnect requested by user.');
    // Reset recovery attempts before triggering
    this.unifiedState.updateRecovery(true, 1); // Signal start of manual recovery
    return this.attemptRecovery('manual_user_request');
  }
}