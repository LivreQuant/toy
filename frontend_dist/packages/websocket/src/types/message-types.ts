// src/types/message-types.ts
// Base interface for common properties
export interface BaseWebSocketMessage {
    type: string;
    timestamp?: number;
    requestId?: string;
  }
  
  // --- Client-to-Server Messages ---
  
  export interface ClientHeartbeatMessage extends BaseWebSocketMessage {
    type: 'heartbeat';
    timestamp: number;
    deviceId: string;
  }
  
  export interface ClientReconnectMessage extends BaseWebSocketMessage {
    type: 'reconnect';
    deviceId: string;
    requestId: string;
  }
    
  export interface ClientStartSimulatorMessage extends BaseWebSocketMessage {
    type: 'start_simulator';
    requestId: string;
    timestamp: number;
    deviceId: string;
  }
  
  export interface ClientStopSimulatorMessage extends BaseWebSocketMessage {
    type: 'stop_simulator';
    requestId: string;
    timestamp: number;
    deviceId: string;
  }
  
  export interface ClientSessionInfoRequest extends BaseWebSocketMessage {
    type: 'request_session';
    requestId: string;
    timestamp: number;
    deviceId: string;
  }
  
  export interface ClientStopSessionRequest extends BaseWebSocketMessage {
    type: 'stop_session';
    requestId: string;
    timestamp: number;
    deviceId: string;
  }
  
  // --- Server-to-Client Messages ---
  
  export interface ServerHeartbeatAckMessage extends BaseWebSocketMessage {
    type: 'heartbeat_ack';
    timestamp: number;
    clientTimestamp: number;
    deviceId: string;
    deviceIdValid: boolean;
    reason: string;
    simulatorStatus: 'RUNNING' | 'STOPPED' | 'STARTING' | 'STOPPING';
  }
  
  export interface ServerReconnectResultMessage extends BaseWebSocketMessage {
    type: 'reconnect_result';
    requestId: string;
    deviceId: string;
    deviceIdValid: boolean;
    reason: string;
    simulatorStatus: 'RUNNING' | 'STOPPED' | 'STARTING' | 'STOPPING';
  }
  
  export interface ServerSessionInfoResponse extends BaseWebSocketMessage {
    type: 'session_info';
    requestId: string;
    userId: string;
    status: string;
    deviceId: string;
    createdAt: number;
    expiresAt: number;
    simulatorStatus: string;
    simulatorId: string | null;
    success?: boolean;
    error?: string;
  }
  
  export interface ServerStopSessionResponse extends BaseWebSocketMessage {
    type: 'session_stopped';
    requestId: string;
    success: boolean;
    error?: string;
  }
  
  export interface ServerSimulatorStartedResponse extends BaseWebSocketMessage {
    type: 'simulator_started';
    requestId: string;
    success: boolean;
    status: string;
    error?: string;
  }
  
  export interface ServerSimulatorStoppedResponse extends BaseWebSocketMessage {
    type: 'simulator_stopped';
    requestId: string;
    success: boolean;
    error?: string;
  }

  export interface ServerExchangeDataMessage extends BaseWebSocketMessage {
    type: 'exchange_data';
    deltaType: 'FULL' | 'DELTA';
    sequence: number;
    timestamp: number;
    data: {
      updateId: string;
      timestamp: number;
      exchangeType: 'EQUITIES' | 'OPTIONS' | 'FUTURES';
      equityData: Array<{
        symbol: string;
        open: number;
        high: number;
        low: number;
        close: number;
        volume: number;
        trade_count: number;
        vwap: number;
        exchange_type: string;
        metadata: Record<string, any>;
      }>;
      orders: Array<{
        orderId: string;
        symbol: string;
        side: 'BUY' | 'SELL';
        quantity: number;
        price: number;
        status: string;
        timestamp: number;
        exchange_type: string;
        metadata: Record<string, any>;
      }>;
      portfolio: {
        positions: Array<{
          symbol: string;
          quantity: number;
          average_price: number;
          market_value: number;
          unrealized_pnl: number;
          metadata: Record<string, any>;
        }>;
        cash_balance: number;
        total_value: number;
        exchange_type: string;
        metadata: Record<string, any>;
      };
      metadata: Record<string, any>;
    };
    compressed: boolean;
    deltaEnabled: boolean;
    compressionEnabled: boolean;
    dataSavings: string;
  }
  
  // --- Union Type for All Messages ---
  export type WebSocketMessage =
    | ClientHeartbeatMessage
    | ClientReconnectMessage
    | ClientStartSimulatorMessage
    | ClientStopSimulatorMessage
    | ClientSessionInfoRequest
    | ClientStopSessionRequest
    | ServerHeartbeatAckMessage
    | ServerReconnectResultMessage
    | ServerExchangeDataMessage
    | ServerSessionInfoResponse
    | ServerStopSessionResponse
    | ServerSimulatorStartedResponse
    | ServerSimulatorStoppedResponse;
  
  // --- Type Guards ---
  export function isHeartbeatAckMessage(msg: WebSocketMessage): msg is ServerHeartbeatAckMessage {
    return msg.type === 'heartbeat_ack';
  }
  
  export function isReconnectResultMessage(msg: WebSocketMessage): msg is ServerReconnectResultMessage {
    return msg.type === 'reconnect_result';
  }

  export function isExchangeDataMessage(msg: WebSocketMessage): msg is ServerExchangeDataMessage {
    return msg.type === 'exchange_data';
  }
  
  export function isSessionInfoResponse(msg: WebSocketMessage): msg is ServerSessionInfoResponse {
    return msg.type === 'session_info';
  }
  
  export function isSessionStoppedResponse(msg: WebSocketMessage): msg is ServerStopSessionResponse {
    return msg.type === 'session_stopped';
  }
  
  export function isSimulatorStartedResponse(msg: WebSocketMessage): msg is ServerSimulatorStartedResponse {
    return msg.type === 'simulator_started';
  }
  
  export function isSimulatorStoppedResponse(msg: WebSocketMessage): msg is ServerSimulatorStoppedResponse {
    return msg.type === 'simulator_stopped';
  }