// src/services/connections/ConnectionTypes.ts

export enum ConnectionState {
    DISCONNECTED = 'DISCONNECTED',
    CONNECTING = 'CONNECTING',
    CONNECTED = 'CONNECTED',
    RECONNECTING = 'RECONNECTING',
    FAILED = 'FAILED'
  }
  
  export interface ConnectionEvent {
    type: ConnectionEventType;
    data: any;
  }
  
  export type ConnectionEventType = 
    | 'state_change' 
    | 'heartbeat' 
    | 'reconnecting' 
    | 'session' 
    | 'simulator' 
    | 'error'
    | 'connection_quality'
    | 'pod_switched'
    | 'all';
  
  export type ConnectionQuality = 'good' | 'degraded' | 'poor';