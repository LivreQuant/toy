// src/services/websocket/websocket-error.ts

import { Logger } from '../../utils/logger';
import { TokenManager } from '../auth/token-manager';
// Assuming CircuitBreaker class is imported if needed for type checking context, but not for calling trip()
import { CircuitBreaker } from '../../utils/circuit-breaker';

// Custom Error Classes (remain the same)
export class WebSocketError extends Error {
  code: string; // e.g., 'CONNECTION_FAILED', 'UNAUTHORIZED', 'PROTOCOL_ERROR', 'HEARTBEAT_TIMEOUT'

  constructor(message: string, code: string) {
    super(message);
    this.name = 'WebSocketError';
    this.code = code;
  }
}

export class NetworkError extends Error {
  type: 'timeout' | 'connection' | 'dns' | 'generic'; // Added generic

  constructor(message: string, type: 'timeout' | 'connection' | 'dns' | 'generic' = 'generic') {
    super(message);
    this.name = 'NetworkError';
    this.type = type;
  }
}

export class AuthenticationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AuthenticationError';
  }
}

// Context interface expected by the handler methods
// Define the shape of the context object passed to the handler methods
// This makes dependencies explicit and improves type safety.
interface WebSocketErrorContext {
    reconnectAttempts?: number; // Optional: Current reconnect attempt count
    circuitBreaker?: CircuitBreaker; // Optional: Pass instance for state checking if needed
    tokenManager: TokenManager; // Required for auth handling
    // --- Callbacks for Actions ---
    disconnect: (reason: string) => void; // Callback to disconnect the WS
    attemptReconnect?: () => void; // Optional: Callback to trigger a reconnect attempt
    triggerLogout: () => void; // Callback to initiate logout process
    manualReconnect?: () => void; // Optional: Callback for manual reconnect (e.g., after token refresh)
    // Add other context methods/properties if needed by handlers
    // tryAlternativeDataSource?: () => Promise<boolean>;
    // initiateOfflineMode?: () => void;
}


/**
 * Handles specific errors related to WebSocket connections.
 * Note: This class is primarily for classifying errors and triggering
 * actions via the provided context callbacks. It delegates general
 * error logging and user notification to the main ErrorHandler.
 */
export class WebSocketErrorHandler {
  private logger: Logger;

  // Constructor remains simple, only needs logger for internal logging if any
  constructor(logger: Logger) {
    this.logger = logger.createChild('WebSocketErrorHandler');
  }

  /**
   * Handles specific WebSocket protocol or connection errors.
   * @param error - The WebSocketError instance.
   * @param context - An object containing necessary dependencies and callbacks.
   */
  public handleWebSocketError(
    error: WebSocketError,
    context: WebSocketErrorContext // Use the defined interface
  ): void {
    this.logger.warn(`Handling WebSocketError - Code: ${error.code}`, { message: error.message });

    switch (error.code) {
      case 'CONNECTION_FAILED':
      case 'CONNECTION_STRATEGY_ERROR': // Treat strategy errors similarly
        this.logger.error('WebSocket connection failed', {
          reason: error.message,
          attempts: context.reconnectAttempts ?? 'N/A' // Use optional chaining/nullish coalescing
        });
        // *** REMOVED: context.circuitBreaker.trip(); ***
        // Circuit breaker trips automatically based on repeated failures in execute().
        // We don't manually trip it here.
        // If the connection failed, the disconnect logic should already be triggered.
        // We might trigger a reconnect attempt if appropriate, handled by the caller or disconnect logic.
        break;

      case 'UNAUTHORIZED':
        // Delegate to the specific authentication error handler
        this.handleAuthenticationError(
          new AuthenticationError(error.message || 'WebSocket unauthorized'),
          context // Pass the same context
        );
        break;

      case 'PROTOCOL_ERROR':
        this.logger.error('WebSocket protocol error', { details: error.message });
        // A protocol error usually means the connection is unusable. Force disconnect.
        context.disconnect('protocol_error');
        // Usually, don't attempt reconnect after a protocol error.
        break;

      case 'HEARTBEAT_TIMEOUT':
         this.logger.error('WebSocket heartbeat timeout', { message: error.message });
         // Heartbeat timeout implies connection loss. Disconnect should have been called.
         // Ensure disconnect is called if not already handled.
         context.disconnect('heartbeat_timeout');
         // Reconnect attempt logic will be handled by the disconnect handler.
         break;

      default:
        this.logger.warn('Unhandled WebSocket error code', { code: error.code, error });
        // Handle as a generic connection issue - disconnect and let reconnect logic decide.
        context.disconnect(`unhandled_ws_error_${error.code}`);
        break;
    }
  }

  /**
   * Handles network-level errors (could be generic fetch errors or specific NetworkError types).
   * @param error - The NetworkError instance or a generic Error.
   * @param context - An object containing necessary dependencies and callbacks.
   */
  public handleNetworkError(
    error: NetworkError | Error, // Accept generic Error too
    context: WebSocketErrorContext // Use the defined interface
    // Add specific context properties if needed:
    // context: WebSocketErrorContext & {
    //   tryAlternativeDataSource?: () => Promise<boolean>,
    //   initiateOfflineMode?: () => void
    // }
  ): void {
    const errorType = error instanceof NetworkError ? error.type : 'generic';
    this.logger.error('Network connectivity issue detected', {
      type: errorType,
      message: error.message
    });

    // Network errors usually lead to disconnection. Ensure disconnect is called.
    context.disconnect(`network_error_${errorType}`);
    // Reconnect logic will be handled by the disconnect handler.

    // Optional: Implement logic for alternative data sources or offline mode if applicable
    // if (context.tryAlternativeDataSource) {
    //   context.tryAlternativeDataSource().then(switched => {
    //     if (!switched && context.initiateOfflineMode) {
    //       context.initiateOfflineMode();
    //     }
    //   });
    // }
  }

  /**
   * Handles authentication errors (e.g., invalid token, session invalidated).
   * Attempts token refresh and reconnect, or triggers logout.
   * @param error - The AuthenticationError instance.
   * @param context - An object containing necessary dependencies and callbacks.
   */
  public handleAuthenticationError(
    error: AuthenticationError,
    context: WebSocketErrorContext // Use the defined interface
  ): void {
    this.logger.error('Authentication error detected', { message: error.message });

    // Always ensure disconnect happens on auth errors
    context.disconnect(`authentication_error: ${error.message}`);

    // Attempt to refresh the token *once*.
    // Check if manualReconnect callback exists before calling refresh
    if (context.manualReconnect) {
        context.tokenManager.refreshAccessToken()
            .then((refreshed: boolean) => {
                if (refreshed) {
                    this.logger.info('Token refreshed successfully after auth error. Triggering manual reconnect.');
                    // Attempt to reconnect manually now that token is potentially valid
                    context.manualReconnect!(); // Use non-null assertion as we checked existence
                } else {
                    this.logger.warn('Token refresh failed after auth error. Triggering logout.');
                    context.triggerLogout(); // Trigger full logout if refresh fails
                }
            })
            .catch(refreshErr => {
                 this.logger.error('Error during token refresh attempt', { refreshErr });
                 context.triggerLogout(); // Trigger logout if refresh itself throws an error
            });
    } else {
         // If manualReconnect isn't provided in context, just trigger logout directly
         this.logger.warn('No manualReconnect callback provided in context. Triggering logout directly on auth error.');
         context.triggerLogout();
    }
  }

  /**
   * Handles generic or unexpected errors caught within the WebSocket manager.
   * @param error - The unknown error object.
   * @param context - An object containing necessary dependencies and callbacks.
   */
   public handleUnknownError(
    error: any, // Type can be anything
    context: WebSocketErrorContext // Use the defined interface
  ): void {
    // Log detailed information about the unexpected error
    this.logger.error('Unexpected error encountered in WebSocket context', {
      errorName: error?.name,
      errorMessage: error?.message,
      errorStack: error?.stack,
      errorDetails: error // Log the whole object if possible
    });

    // Treat unknown errors cautiously - disconnect the connection
    context.disconnect('unexpected_error');

    // Optionally attempt a reconnect, but be wary of error loops
    if (context.attemptReconnect) {
        this.logger.warn('Attempting reconnect after unexpected error.');
        context.attemptReconnect();
    }
  }
}
