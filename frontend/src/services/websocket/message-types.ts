// src/services/websocket/message-types.ts

// Base interface for common properties like type and optional requestId/timestamp
export interface BaseWebSocketMessage {
    type: string;       // Discriminator field
    requestId?: string; // Optional: For request-response correlation
    timestamp?: number; // Optional: Server timestamp in milliseconds
}

// --- Client-to-Server Messages (Examples) ---

export interface ClientHeartbeatMessage extends BaseWebSocketMessage {
    type: 'heartbeat';
    // Client might send its timestamp for RTT calculation if needed
    // clientTimestamp: number;
}

export interface SubscribeMessage extends BaseWebSocketMessage {
    type: 'subscribe';
    channel: string; // e.g., 'market_data.BTC/USD', 'user_orders'
    // Optional parameters specific to the subscription
    params?: Record<string, any>;
}

export interface UnsubscribeMessage extends BaseWebSocketMessage {
    type: 'unsubscribe';
    channel: string;
}

// Example for a generic request needing a response
export interface GenericRequestMessage extends BaseWebSocketMessage {
    type: 'get_portfolio' | 'get_settings' | 'submit_order_ws'; // Example request types via WS
    requestId: string; // Required for requests needing response
    payload?: any;     // Request-specific data
}


// --- Server-to-Client Messages ---

// Heartbeat Response (acknowledging client heartbeat or server-initiated ping)
export interface ServerHeartbeatMessage extends BaseWebSocketMessage {
    type: 'heartbeat'; // Server can also send 'heartbeat' type
    deviceId?: string; // Optional: Server might echo deviceId for validation
    simulatorStatus?: string; // Optional: Include sim status in heartbeat
    // Include original clientTimestamp if server calculates RTT server-side
    // clientTimestamp?: number;
}


// Session Status / Control Messages
export interface SessionInvalidatedMessage extends BaseWebSocketMessage {
    type: 'session_invalidated';
    reason: string; // e.g., 'token_expired', 'duplicate_login', 'server_shutdown'
}

export interface SessionReadyResponseMessage extends BaseWebSocketMessage {
    type: 'session_ready_response'; // Response to client indicating session is ready after connect
    status: 'ready' | 'pending' | 'error';
    message?: string; // Optional message
}


// Response message for specific client requests sent via WebSocket
export interface ResponseMessage extends BaseWebSocketMessage {
    type: 'response';   // Generic response type
    requestId: string;  // Required: Correlates to a client request's requestId
    success: boolean;   // Indicates if the request operation was successful
    error?: {           // Included if success is false
        code: string;   // e.g., 'INVALID_PARAM', 'NOT_FOUND', 'PERMISSION_DENIED'
        message: string; // Human-readable error message
    };
    data?: any;         // Optional data payload if success is true
}

// --- Data Push Messages ---

// Market Data Update
export interface ExchangeDataMessage extends BaseWebSocketMessage {
    type: 'exchange_data';
    data: {
        timestamp: number; // Timestamp of the data snapshot
        symbols: Record<string, { // Keyed by symbol (e.g., 'BTC/USD')
            price: number;
            open?: number;
            high?: number;
            low?: number;
            close?: number; // Previous close
            volume?: number;
            // Add other relevant fields: bid, ask, change, etc.
        }>;
    };
}

// Order Update (real-time status changes for user's orders)
export interface OrderUpdateMessage extends BaseWebSocketMessage {
    type: 'order_update';
    data: { // Structure matches the Order type in src/types/index.ts?
        orderId: string;
        symbol: string;
        status: string; // Use specific status enum if defined (e.g., OrderStatus)
        side: 'BUY' | 'SELL';
        type: 'MARKET' | 'LIMIT';
        quantity: number;
        filledQty: number;
        remainingQty: number;
        limitPrice?: number;
        avgFillPrice?: number;
        timestamp: number; // Timestamp of this update
        // Include reason for rejection/cancellation if applicable
        rejectReason?: string;
    };
}

// Portfolio Update (changes in user's positions or cash)
export interface PortfolioDataMessage extends BaseWebSocketMessage {
    type: 'portfolio_data';
    data: {
        timestamp: number;
        cash: number;
        positions: Record<string, { // Keyed by symbol
            symbol: string;
            quantity: number;
            avgPrice: number;
            marketValue?: number; // Optional: calculated server-side?
            unrealizedPnl?: number; // Optional: calculated server-side?
        }>;
        // Maybe include overall portfolio value, margin info, etc.
    };
}

// Risk Data Update (changes in risk metrics)
export interface RiskDataMessage extends BaseWebSocketMessage {
    type: 'risk_data';
    data: {
        timestamp: number;
        portfolioRiskLevel: 'low' | 'medium' | 'high'; // Example categorical risk
        buyingPower: number;
        // Add other relevant risk metrics
        // symbolRisks?: Record<string, number>;
        // exposures?: Record<string, number>;
    };
}


// --- Union Type for All Possible Incoming Messages (Server -> Client) ---
// Add *all* expected message types from the server here
export type WebSocketMessage =
    | ServerHeartbeatMessage
    | SessionInvalidatedMessage
    | SessionReadyResponseMessage
    | ResponseMessage
    | ExchangeDataMessage
    | OrderUpdateMessage
    | PortfolioDataMessage
    | RiskDataMessage;
    // Add any other message types the server might send


// --- Type Guard Functions (Essential for handling messages correctly) ---

export function isServerHeartbeatMessage(msg: WebSocketMessage): msg is ServerHeartbeatMessage {
    return msg.type === 'heartbeat';
}
// Alias for clarity, as client sends heartbeat too, but server response confirms liveliness
export const isHeartbeatMessage = isServerHeartbeatMessage;

export function isSessionInvalidatedMessage(msg: WebSocketMessage): msg is SessionInvalidatedMessage {
    return msg.type === 'session_invalidated';
}

export function isSessionReadyResponseMessage(msg: WebSocketMessage): msg is SessionReadyResponseMessage {
    return msg.type === 'session_ready_response';
}

export function isResponseMessage(msg: WebSocketMessage): msg is ResponseMessage {
    return msg.type === 'response' && typeof (msg as any).requestId === 'string';
}

export function isExchangeDataMessage(msg: WebSocketMessage): msg is ExchangeDataMessage {
    return msg.type === 'exchange_data' && typeof (msg as any).data?.symbols === 'object';
}

export function isOrderUpdateMessage(msg: WebSocketMessage): msg is OrderUpdateMessage {
    return msg.type === 'order_update' && typeof (msg as any).data?.orderId === 'string';
}

export function isPortfolioDataMessage(msg: WebSocketMessage): msg is PortfolioDataMessage {
    return msg.type === 'portfolio_data' && typeof (msg as any).data?.cash === 'number';
}

export function isRiskDataMessage(msg: WebSocketMessage): msg is RiskDataMessage {
     return msg.type === 'risk_data' && typeof (msg as any).data?.buyingPower === 'number';
}

// Add type guards for any other message types you define