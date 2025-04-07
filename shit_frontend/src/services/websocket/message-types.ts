// src/services/websocket/message-types.ts
// Base interfaces for common properties
export interface BaseWebSocketMessage {
    type: string;
    requestId?: string;
    timestamp?: number;
  }
  
  // Authentication and session messages
  export interface HeartbeatMessage extends BaseWebSocketMessage {
    type: 'heartbeat';
    deviceId: string;
    simulatorStatus: string;
  }
  
  export interface SessionInvalidatedMessage extends BaseWebSocketMessage {
    type: 'session_invalidated';
    reason: string;
  }
  
  export interface SessionReadyResponseMessage extends BaseWebSocketMessage {
    type: 'session_ready_response';
    status: string;
  }
  
  // Response message for requests
  export interface ResponseMessage extends BaseWebSocketMessage {
    type: 'response';
    requestId: string; // Required for responses
    success: boolean;
    error?: {
      code: string;
      message: string;
    };
    data?: any;
  }
  
  // Data messages
  export interface ExchangeDataMessage extends BaseWebSocketMessage {
    type: 'exchange_data';
    data: {
      timestamp: number;
      symbols: Record<string, {
        price: number;
        open: number;
        high: number;
        low: number;
        close: number;
        volume: number;
      }>;
    };
  }
  
  export interface OrderUpdateMessage extends BaseWebSocketMessage {
    type: 'order_update';
    data: {
      orderId: string;
      symbol: string;
      status: string;
      filledQty: number;
      remainingQty: number;
      price?: number;
      timestamp: number;
    };
  }
  
  export interface PortfolioDataMessage extends BaseWebSocketMessage {
    type: 'portfolio_data';
    data: {
      positions: Record<string, {
        symbol: string;
        quantity: number;
        avgPrice: number;
        marketValue: number;
        unrealizedPnl: number;
      }>;
      cash: number;
      timestamp: number;
    };
  }
  
  export interface RiskDataMessage extends BaseWebSocketMessage {
    type: 'risk_data';
    data: {
      portfolioRisk: number;
      symbolRisks: Record<string, number>;
      exposures: Record<string, number>;
      timestamp: number;
    };
  }
  
  // Union type for all possible messages
  export type WebSocketMessage = 
    | HeartbeatMessage
    | SessionInvalidatedMessage
    | SessionReadyResponseMessage
    | ResponseMessage
    | ExchangeDataMessage
    | OrderUpdateMessage
    | PortfolioDataMessage
    | RiskDataMessage;
  
  // Type guard functions
  export function isHeartbeatMessage(message: WebSocketMessage): message is HeartbeatMessage {
    return message.type === 'heartbeat';
  }
  
  export function isExchangeDataMessage(message: WebSocketMessage): message is ExchangeDataMessage {
    return message.type === 'exchange_data';
  }
  
  export function isOrderUpdateMessage(message: WebSocketMessage): message is OrderUpdateMessage {
    return message.type === 'order_update';
  }
  
  export function isResponseMessage(message: WebSocketMessage): message is ResponseMessage {
    return message.type === 'response';
  }
  
  // Add other type guards as needed