// src/services/websocket/message-types.ts

// Base interface for common properties
export interface BaseWebSocketMessage {
    type: string;
    timestamp?: number;
}

// --- Client-to-Server Messages ---

export interface ClientHeartbeatMessage extends BaseWebSocketMessage {
    type: 'heartbeat';
    timestamp: number;
    deviceId: string;
    connectionQuality: 'good' | 'degraded' | 'poor';
    sessionStatus: 'active' | 'expired' | 'pending';
    simulatorStatus: 'running' | 'stopped' | 'starting' | 'stopping';
}

export interface ClientReconnectMessage extends BaseWebSocketMessage {
    type: 'reconnect';
    deviceId: string;
    sessionToken: string;
    requestId: string;
}

// --- Server-to-Client Messages ---

export interface ServerHeartbeatAckMessage extends BaseWebSocketMessage {
    type: 'heartbeat_ack';
    timestamp: number;
    clientTimestamp: number;
    deviceId: string;
    deviceIdValid: boolean;
    connectionQualityUpdate: 'good' | 'degraded' | 'poor';
    sessionStatus: 'valid' | 'invalid' | 'pending';
    simulatorStatus: 'running' | 'stopped' | 'starting' | 'stopping';
}

export interface ServerReconnectResultMessage extends BaseWebSocketMessage {
    type: 'reconnect_result';
    requestId: string;
    success: boolean;
    deviceId: string;
    deviceIdValid: boolean;
    message?: string;
    sessionStatus: 'valid' | 'invalid' | 'pending';
    simulatorStatus: 'running' | 'stopped' | 'starting' | 'stopping';
}

export interface ServerExchangeDataStatusMessage extends BaseWebSocketMessage {
    type: 'exchange_data_status';
    timestamp: number;
    symbols: Record<string, {
        price: number;
        change: number;
        volume: number;
    }>;
    userOrders?: Record<string, {
        orderId: string;
        status: string;
        filledQty: number;
    }>;
    userPositions?: Record<string, {
        symbol: string;
        quantity: number;
        value: number;
    }>;
}

// --- Union Type for All Possible Messages ---
export type WebSocketMessage =
    | ClientHeartbeatMessage
    | ClientReconnectMessage
    | ServerHeartbeatAckMessage
    | ServerReconnectResultMessage
    | ServerExchangeDataStatusMessage;

// --- Type Guard Functions ---
export function isServerHeartbeatAckMessage(msg: WebSocketMessage): msg is ServerHeartbeatAckMessage {
    return msg.type === 'heartbeat_ack';
}

export function isServerReconnectResultMessage(msg: WebSocketMessage): msg is ServerReconnectResultMessage {
    return msg.type === 'reconnect_result';
}

export function isServerExchangeDataStatusMessage(msg: WebSocketMessage): msg is ServerExchangeDataStatusMessage {
    return msg.type === 'exchange_data_status';
}