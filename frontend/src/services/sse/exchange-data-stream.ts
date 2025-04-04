// src/services/sse/exchange-data-stream.ts
import { SSEManager } from './sse-manager';
import { TokenManager } from '../auth/token-manager';
import { WebSocketManager } from '../websocket/websocket-manager';
import { EventEmitter } from '../../utils/event-emitter';
import { 
  UnifiedConnectionState, 
  ConnectionServiceType, 
  ConnectionStatus 
} from '../connection/unified-connection-state';

export interface ExchangeDataOptions {
  reconnectMaxAttempts?: number;
  debugMode?: boolean;
}

export class ExchangeDataStream extends EventEmitter {
  private sseManager: SSEManager;
  private exchangeData: Record<string, any> = {};
  private tokenManager: TokenManager;
  private webSocketManager: WebSocketManager;
  private unifiedState: UnifiedConnectionState;
  private debugMode: boolean;
  
  constructor(
    tokenManager: TokenManager, 
    webSocketManager: WebSocketManager,
    unifiedState: UnifiedConnectionState,
    options: ExchangeDataOptions = {}
  ) {
    super();
    
    this.tokenManager = tokenManager;
    this.webSocketManager = webSocketManager;
    this.unifiedState = unifiedState;
    this.debugMode = options.debugMode || false;
    
    this.sseManager = new SSEManager(tokenManager, unifiedState, {
      reconnectMaxAttempts: options.reconnectMaxAttempts || 15,
      debugMode: this.debugMode
    });
  
    // Set up SSE manager event listeners
    this.sseManager.on('exchange-data', this.handleExchangeData.bind(this));
    this.sseManager.on('error', this.handleError.bind(this));
    
    // Forward relevant SSE events
    ['connected', 'disconnected', 'reconnecting'].forEach(event => {
      this.sseManager.on(event, (data: any) => this.emit(event, data));
    });
  }
  
  public isConnected(): boolean {
    // Check if WebSocket is connected first
    const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    if (wsState.status !== ConnectionStatus.CONNECTED) {
      return false;
    }
    
    // Then check SSE connection
    const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
    return sseState.status === ConnectionStatus.CONNECTED;
  }
  
  public async connect(): Promise<boolean> {
    // Always check WebSocket connection first - don't connect SSE if WebSocket is down
    const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    if (wsState.status !== ConnectionStatus.CONNECTED) {
      this.emit('error', { 
        error: 'Cannot connect SSE - WebSocket is not connected',
        webSocketStatus: wsState
      });
      return false;
    }
    
    if (this.debugMode) {
      console.log('ExchangeDataStream - Connecting to unified data stream');
    }
  
    // Validate authentication
    const token = await this.tokenManager.getAccessToken();
    if (!token) {
      this.emit('error', { error: 'Authentication required for exchange data stream' });
      return false;
    }
    
    try {
        const connected = await this.sseManager.connect();
        if (this.debugMode) {
          console.log('ExchangeDataStream - Connection Result:', connected);
        }
        return connected;
    } catch (error) {
        console.error('ExchangeDataStream - Connection Error:', error);
        return false;
    }
  }
  
  public getConnectionStatus(): {
    connected: boolean;
    connecting: boolean;
    webSocketConnected: boolean;
  } {
    const sseState = this.unifiedState.getServiceState(ConnectionServiceType.SSE);
    const wsState = this.unifiedState.getServiceState(ConnectionServiceType.WEBSOCKET);
    
    return {
      connected: sseState.status === ConnectionStatus.CONNECTED,
      connecting: sseState.status === ConnectionStatus.CONNECTING,
      webSocketConnected: wsState.status === ConnectionStatus.CONNECTED
    };
  }
  
  private handleExchangeData(data: any): void {
    try {
        if (this.debugMode) {
          console.log('Received exchange data:', data);
        }

        // Update exchange data
        this.exchangeData = { ...data };
        
        // Emit exchange data update
        this.emit('exchange-data', this.exchangeData);
    } catch (error) {
        console.error('Error processing exchange data:', error, 'Raw data:', data);
    }
  }

  public disconnect(): void {
    this.sseManager.close();
  }
  
  public getExchangeData(): Record<string, any> {
    return { ...this.exchangeData };
  }
  
  private handleError(error: any): void {
    console.error('Exchange data stream error:', error);
    this.emit('error', error);
  }
    
  public dispose(): void {
    this.disconnect();
    this.removeAllListeners();
  }
}