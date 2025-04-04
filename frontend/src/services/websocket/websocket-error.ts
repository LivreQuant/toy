import { Logger } from '../../utils/logger';

export class WebSocketError extends Error {
  code: string;

  constructor(message: string, code: string) {
    super(message);
    this.name = 'WebSocketError';
    this.code = code;
  }
}

export class NetworkError extends Error {
  type: 'timeout' | 'connection' | 'dns';

  constructor(message: string, type: 'timeout' | 'connection' | 'dns') {
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

export class WebSocketErrorHandler {
  private logger: Logger;

  constructor(logger: Logger) {
    this.logger = logger;
  }

  public handleWebSocketError(
    error: WebSocketError, 
    context: {
      reconnectAttempts: number,
      circuitBreaker: any,
      tokenManager: any,
      disconnect: (reason: string) => void,
      attemptReconnect: () => void,
      triggerLogout: () => void,
      manualReconnect: () => void
    }
  ): void {
    switch (error.code) {
      case 'CONNECTION_FAILED':
        this.logger.error('WebSocket connection failed', {
          reason: error.message,
          attempts: context.reconnectAttempts
        });
        context.circuitBreaker.trip();
        break;
      case 'UNAUTHORIZED':
        this.handleAuthenticationError(
          new AuthenticationError('WebSocket unauthorized'),
          {
            tokenManager: context.tokenManager,
            manualReconnect: context.manualReconnect,
            triggerLogout: context.triggerLogout
          }
        );
        break;
      case 'PROTOCOL_ERROR':
        this.logger.error('WebSocket protocol error', {
          details: error.message
        });
        context.disconnect('protocol_error');
        break;
      default:
        this.logger.warn('Unhandled WebSocket error', { error });
    }
  }

  public handleNetworkError(
    error: NetworkError,
    context: {
      tryAlternativeDataSource: () => Promise<boolean>,
      initiateOfflineMode: () => void
    }
  ): void {
    this.logger.error('Network connectivity issue', {
      type: error.type,
      message: error.message
    });

    context.tryAlternativeDataSource()
      .then(switched => {
        if (!switched) {
          context.initiateOfflineMode();
        }
      });
  }

  public handleAuthenticationError(
    error: AuthenticationError,
    context: {
      tokenManager: TokenManager,
      manualReconnect: () => void,
      triggerLogout: () => void
    }
  ): void {
    this.logger.error('Authentication failed', {
      message: error.message
    });

    // Use the centralized token refresh method
    context.tokenManager.refreshAccessToken()
      .then(refreshed => {
        if (refreshed) {
          context.manualReconnect();
        } else {
          context.triggerLogout();
        }
      });
  }

  public handleUnknownError(
    error: any,
    context: {
      logger: Logger,
      disconnect: (reason: string) => void,
      attemptReconnect: () => void
    }
  ): void {
    context.logger.error('Unexpected error in WebSocket manager', {
      errorName: error.name,
      errorMessage: error.message,
      errorStack: error.stack
    });

    context.disconnect('unexpected_error');
    context.attemptReconnect();
  }
}