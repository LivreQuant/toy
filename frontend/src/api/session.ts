// src/api/session.ts
import { HttpClient } from './http-client';
import { TokenManager } from '../services/auth/token-manager';
import { SessionManager } from '../services/session/session-manager';

export interface SessionResponse {
  success: boolean;
  isMaster: boolean;
  errorMessage?: string;
}

export interface SessionStateResponse {
  success: boolean;
  simulatorId: string;
  simulatorEndpoint: string;
  simulatorStatus: string;
  sessionCreatedAt: number;
  lastActive: number;
}

export class SessionApi {
  private client: HttpClient;
  private tokenManager: TokenManager;
  
  constructor(client: HttpClient, tokenManager: TokenManager) {
    this.client = client;
    this.tokenManager = tokenManager;
  }

  async createSession(): Promise<SessionResponse> {
    const deviceId = SessionManager.getDeviceId();
    return this.client.post<SessionResponse>('/sessions', {
      deviceId: deviceId
    });
  }
  
  async getSessionState(): Promise<SessionStateResponse> {
    return this.client.get<SessionStateResponse>('/sessions');
  }

  async reconnectSession(reconnectAttempt: number): Promise<SessionResponse> {
    const deviceId = SessionManager.getDeviceId();
    return this.client.post<SessionResponse>('/sessions/reconnect', { 
      deviceId,
      reconnectAttempt 
    });
  }
}