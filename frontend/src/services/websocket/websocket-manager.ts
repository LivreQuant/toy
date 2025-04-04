// src/services/websocket/websocket-manager.ts
// This file is based on the previous refactoring ('refactored_websocket_manager_state_clarity')
// The only change is ensuring no 'claim_master' listener is present.

import { config } from '../../config';
import { EventEmitter } from '../../utils/event-emitter';
import { BackoffStrategy } from '../../utils/backoff-strategy';
import { CircuitBreaker, CircuitState } from '../../utils/circuit-breaker';
import { TokenManager } from '../auth/token-manager';
import { ConnectionStrategy, ConnectionStrategyDependencies } from './connection-strategy';
import { HeartbeatManager } from './heartbeat-manager';
import {
    WebSocketErrorHandler,
    WebSocketError,
    NetworkError,
    AuthenticationError
} from './websocket-error';
import { ErrorHandler as UtilsErrorHandler, ErrorSeverity } from '../../utils/error-handler';
import { WebSocketMessageHandler } from './message-handler';
import { DeviceIdManager } from '../../utils/device-id-manager';
import { MetricTracker } from '../../utils/metric-tracker'; // Corrected path if needed
import { Logger } from '../../utils/logger';
import {
    WebSocketOptions,
    ConnectionMetrics,
    ConnectionQuality as WSConnectionQuality,
    HeartbeatData
} from './types';
import {
    UnifiedConnectionState,
    ConnectionServiceType,
    ConnectionStatus,
    ConnectionQuality
} from '../connection/unified-connection-state';
import { Disposable } from '../../utils/disposable';

export class WebSocketManager extends EventEmitter implements Disposable {
    private connectionStrategy: ConnectionStrategy;
    private heartbeatManager: HeartbeatManager | null = null;
    private messageHandler: WebSocketMessageHandler;
    private tokenManager: TokenManager;
    private metricTracker: MetricTracker;
    private errorHandler: WebSocketErrorHandler;
    private logger: Logger;
    private unifiedState: UnifiedConnectionState;

    private backoffStrategy: BackoffStrategy;
    private circuitBreaker: CircuitBreaker;
    private reconnectTimer: number | null = null;
    private reconnectAttempts: number = 0;
    private maxReconnectAttempts: number = 10;
    private isDisposed: boolean = false;

    private connectionMetrics: ConnectionMetrics = { latency: 0, bandwidth: 0, packetLoss: 0 };
    private currentConnectionQuality: WSConnectionQuality = WSConnectionQuality.DISCONNECTED;

    constructor(
        tokenManager: TokenManager,
        unifiedState: UnifiedConnectionState,
        logger: Logger,
        options: WebSocketOptions = {}
    ) {
        super();
        this.tokenManager = tokenManager;
        this.unifiedState = unifiedState;
        this.logger = logger.createChild('WebSocketManager');
        this.logger.info("WebSocketManager Initializing...");

        this.metricTracker = new MetricTracker(this.logger);
        this.errorHandler = new WebSocketErrorHandler(this.logger);

        this.backoffStrategy = new BackoffStrategy(/*...*/);
        this.circuitBreaker = new CircuitBreaker(/*...*/);
        this.circuitBreaker.onStateChange(/*...*/);

        const strategyDeps: ConnectionStrategyDependencies = {
            tokenManager,
            eventEmitter: this,
            logger: this.logger,
            options
        };
        this.connectionStrategy = new ConnectionStrategy(strategyDeps);

        // Pass logger to MessageHandler
        this.messageHandler = new WebSocketMessageHandler(this, this.logger);
        this.maxReconnectAttempts = options.reconnectMaxAttempts ?? 10;

        this.setupListeners();
        this.logger.info("WebSocketManager Initialized.");
    }

    // Centralized setup for internal event listeners
    private setupListeners(): void {
        this.logger.info("Setting up WebSocketManager listeners...");
        this.on('error', this.routeErrorToHandler.bind(this));
        this.on('ws_disconnected_internal', this.handleDisconnectEvent.bind(this));
        this.on('ws_error_internal', (errorData: any) => {
            const wsError = new WebSocketError(errorData.message || 'Connection strategy error', 'CONNECTION_FAILED');
            this.routeErrorToHandler(wsError);
        });

        // Heartbeat events
        this.on('heartbeat', this.handleHeartbeatEvent.bind(this));
        this.on('heartbeat_timeout', this.handleHeartbeatTimeout.bind(this));

        // Session invalidation (now handles superseded tabs via backend message)
        this.on('session_invalidated', this.handleSessionInvalidated.bind(this));

        // NO LISTENER for 'claim_master' needed here anymore
        // this.on('claim_master', this.handleClaimMaster.bind(this)); // REMOVED

        // Logout events
        this.on('force_logout', (reason: string) => {
            this.logger.warn(`Force logout event received: ${reason}`);
            this.disconnect('force_logout');
        });

        // Listen for specific message types emitted by MessageHandler if needed
        this.on('order_update', (data: any) => {
             this.logger.debug('Order update received via WebSocketManager event.');
             // Forward or process as needed
        });
         this.on('exchange_data', (data: any) => {
             this.logger.debug('Exchange data received via WebSocketManager event.');
              // Forward or process as needed
        });
        this.on('session_ready_response', (data: any) => {
             this.logger.debug('Session ready response received via WebSocketManager event.');
              // Forward or process as needed
        });
         this.on('message_error', (errorInfo: any) => {
             this.logger.error('Message handler reported an error.', errorInfo);
             // Decide if this needs specific handling or just logging
        });
         this.on('unknown_message', (message: any) => {
             this.logger.warn('Received message of unknown type from handler.', { type: message?.type });
        });
    }

    /**
     * Central routing point for all errors caught or emitted within WebSocketManager.
     * Delegates handling to the injected WebSocketErrorHandler instance.
     * @param error - The error object.
     */
    private routeErrorToHandler(error: any): void {
        // ... (implementation remains the same as previous refactor) ...
        if (this.isDisposed) return;
        this.logger.error("Routing error to WebSocketErrorHandler", { errorName: error?.name, errorMessage: error?.message });
        const handlerContext = { /* ... context ... */ }; // Assembled as before
        // Delegate to appropriate handler method...
        if (error instanceof WebSocketError) this.errorHandler.handleWebSocketError(error, handlerContext);
        else if (error instanceof NetworkError) this.errorHandler.handleNetworkError(error, handlerContext);
        else if (error instanceof AuthenticationError) this.errorHandler.handleAuthenticationError(error, handlerContext);
        else { /* Handle unknown */ }
        // Update unified state...
    }


    // Handles the 'disconnected' event emitted internally by ConnectionStrategy
    private handleDisconnectEvent(details: { code: number; reason: string; wasClean: boolean }): void {
        // ... (implementation remains the same - updates state, potentially calls attemptReconnect) ...
        if (this.isDisposed) return;
        this.logger.warn(`WebSocket disconnected event received. Code: ${details.code}, Reason: ${details.reason}, Clean: ${details.wasClean}`);
        this.heartbeatManager?.stop();
        this.heartbeatManager = null;
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, { /* ... state ... */ });
        const shouldAttemptReconnect = details.code !== 1000 && this.circuitBreaker.getState() !== CircuitState.OPEN;
        if (shouldAttemptReconnect) this.attemptReconnect();
        else { /* Reset counters */ }
    }

    // Handles the 'heartbeat' event (likely a response from server)
    private handleHeartbeatEvent(data: HeartbeatData): void {
        // ... (implementation remains the same - updates unified state, WS quality) ...
        if (this.isDisposed) return;
        this.heartbeatManager?.handleHeartbeatResponse();
        const now = Date.now();
        const latency = data.timestamp ? (now - data.timestamp) : this.connectionMetrics.latency;
        this.unifiedState.updateHeartbeat(now, latency);
        if (data.simulatorStatus) this.unifiedState.updateSimulatorStatus(data.simulatorStatus);
        this.updateWsConnectionQuality(latency);
    }

    // Handle heartbeat timeout event
    private handleHeartbeatTimeout(): void {
        // ... (implementation remains the same - routes error, disconnects strategy) ...
        if (this.isDisposed) return;
        this.logger.error('Heartbeat timeout detected.');
        const error = new WebSocketError('Connection lost (heartbeat timeout).', 'HEARTBEAT_TIMEOUT');
        this.routeErrorToHandler(error);
        this.connectionStrategy.disconnect('heartbeat_timeout');
    }

    // Handle session invalidation message from server
    // This now handles the case where the backend invalidates due to a superseded connection
    private handleSessionInvalidated(details: { reason: string }): void {
        if (this.isDisposed) return;
        this.logger.error(`Session invalidated by server. Reason: ${details.reason}`);
        const error = new AuthenticationError(`Session invalidated: ${details.reason}. Please log in again.`);
        // Route the auth error - the handler should trigger logout
        this.routeErrorToHandler(error);
    }

    // Update internal WS quality state and emit specific event
    private updateWsConnectionQuality(latency: number): void {
        // ... (implementation remains the same) ...
        if (this.isDisposed) return;
        const newQuality = this.calculateWsConnectionQuality(latency);
        if (newQuality !== this.currentConnectionQuality) {
             this.logger.info(`Internal WebSocket connection quality changed: ${this.currentConnectionQuality} -> ${newQuality}`);
             this.currentConnectionQuality = newQuality;
             this.emit('connection_quality_changed', this.currentConnectionQuality);
        }
    }

    // Internal calculation for WebSocket-specific quality levels
    private calculateWsConnectionQuality(latency: number): WSConnectionQuality {
        // ... (implementation remains the same) ...
        if (latency < 0) return WSConnectionQuality.DISCONNECTED;
        if (latency <= 100) return WSConnectionQuality.EXCELLENT;
        // ... etc ...
        return WSConnectionQuality.POOR;
    }

    // Triggers logout process (called potentially by WebSocketErrorHandler)
    private triggerLogout(reason: string = 'unknown'): void {
        // ... (implementation remains the same) ...
        if (this.isDisposed) return;
        this.logger.warn(`Triggering logout. Reason: ${reason}`);
        this.disconnect(`logout: ${reason}`);
        this.tokenManager.clearTokens();
        UtilsErrorHandler.handleAuthError('Session ended. Please log in again.', ErrorSeverity.HIGH);
        this.emit('force_logout', reason);
    }


    /**
     * Establishes the WebSocket connection. Relies on UnifiedConnectionState for status.
     * @returns True if connection attempt is successful, false otherwise.
     */
    public async connect(): Promise<boolean> {
        // ... (implementation remains the same as previous refactor) ...
        if (this.isDisposed) return false;
        const currentState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status;
        if (currentState === ConnectionStatus.CONNECTED || currentState === ConnectionStatus.CONNECTING) return currentState === ConnectionStatus.CONNECTED;
        this.logger.info("WebSocket connect requested.");
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, { status: ConnectionStatus.CONNECTING, /*...*/ });
        try {
            const ws = await this.circuitBreaker.execute(async () => { /*...*/ });
            // Success handling...
            this.logger.info("WebSocket connection established successfully.");
            this.heartbeatManager = new HeartbeatManager({ ws, /*...*/ });
            this.heartbeatManager.start();
            // Update unified state...
            this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, { status: ConnectionStatus.CONNECTED, /*...*/ });
            return true;
        } catch (error: any) {
            // Failure handling...
            this.logger.error(`WebSocket connection failed overall. Reason: ${error.message}`);
            this.routeErrorToHandler(error);
            return false;
        }
    }

    /**
     * Sends a message. Checks WebSocket readyState directly.
     * @param message - The message object to send.
     * @throws {Error} If the WebSocket is not open.
     */
    public send(message: any): void {
        // ... (implementation remains the same) ...
        if (this.isDisposed) throw new Error("WebSocketManager is disposed.");
        const ws = this.connectionStrategy.getWebSocket();
        if (ws && ws.readyState === WebSocket.OPEN) { /* Send */ }
        else { /* Handle error */ }
    }

    /**
     * Disconnects the WebSocket connection intentionally. Updates UnifiedConnectionState.
     * @param reason - A string indicating the reason for disconnection.
     */
    public disconnect(reason: string = 'user_disconnect'): void {
        // ... (implementation remains the same) ...
        if (this.isDisposed) return;
        this.logger.warn(`WebSocket disconnect requested. Reason: ${reason}`);
        this.stopReconnectTimer();
        this.heartbeatManager?.stop();
        this.connectionStrategy.disconnect();
        // Update unified state...
        const currentState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
        if (currentState.status !== ConnectionStatus.DISCONNECTED) { /* Update state */ }
        // Reset resilience mechanisms...
    }

    /**
     * Cleans up resources used by the WebSocketManager.
     */
    public dispose(): void {
        // ... (implementation remains the same) ...
        if (this.isDisposed) return;
        this.logger.warn("Disposing WebSocketManager...");
        this.isDisposed = true;
        this.disconnect('manager_disposed');
        this.removeAllListeners();
        // ... cleanup ...
        this.logger.warn("WebSocketManager disposed.");
    }

    // Method to explicitly stop any active reconnect timer
    private stopReconnectTimer(): void {
        // ... (implementation remains the same) ...
        if (this.reconnectTimer !== null) { /* Clear timer */ }
    }

    /**
     * Attempts to reconnect the WebSocket connection. Updates UnifiedConnectionState.
     */
    private attemptReconnect(): void {
        // ... (implementation remains the same - checks circuit breaker, max attempts, updates state, schedules connect) ...
        if (this.isDisposed || this.reconnectTimer !== null) return;
        if (this.circuitBreaker.getState() === CircuitState.OPEN) { /* Handle open circuit */ return; }
        if (this.reconnectAttempts >= this.maxReconnectAttempts) { /* Handle max attempts */ return; }
        this.reconnectAttempts++;
        const delay = this.backoffStrategy.nextBackoffTime();
        this.logger.info(`Scheduling WebSocket reconnect attempt...`);
        // Update unified state...
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, { status: ConnectionStatus.RECOVERING, /*...*/ });
        this.unifiedState.updateRecovery(true, this.reconnectAttempts);
        this.emit('reconnecting', { /*...*/ });
        this.reconnectTimer = window.setTimeout(async () => { /*...*/ }, delay);
    }

    /**
     * Initiates a manual reconnection attempt immediately. Updates UnifiedConnectionState.
     */
    public manualReconnect(): void {
        // ... (implementation remains the same - resets state, calls connect) ...
        if (this.isDisposed) return;
        this.logger.warn('Manual reconnect requested.');
        this.stopReconnectTimer();
        this.reconnectAttempts = 0;
        this.backoffStrategy.reset();
        this.circuitBreaker.reset();
        // Update unified state...
        this.unifiedState.updateServiceState(ConnectionServiceType.WEBSOCKET, { status: ConnectionStatus.RECOVERING, /*...*/ });
        this.unifiedState.updateRecovery(true, 1);
        this.connect();
    }

    /**
     * Gets the current health status, deriving status from UnifiedConnectionState.
     * @returns An object containing status, quality, and error information.
     */
    public getConnectionHealth() {
        // ... (implementation remains the same as previous refactor) ...
         if (this.isDisposed) return { status: 'disconnected', /*...*/ };
         const serviceState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
         let statusString: 'connected' | 'connecting' | 'recovering' | 'disconnected';
         switch (serviceState.status) { /* Map enum to string */ }
         return { status: statusString, quality: this.currentConnectionQuality, error: serviceState.error };
    }

    /**
     * Checks if the WebSocket is connecting or recovering based on UnifiedConnectionState.
     * @returns True if connecting or recovering, false otherwise.
     */
    public isConnectingOrRecovering(): boolean {
        // ... (implementation remains the same as previous refactor) ...
        if (this.isDisposed) return false;
        const status = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET).status;
        return status === ConnectionStatus.CONNECTING || status === ConnectionStatus.RECOVERING;
    }

    // Implement [Symbol.dispose] for Disposable interface
    [Symbol.dispose](): void {
        this.dispose();
    }
}
