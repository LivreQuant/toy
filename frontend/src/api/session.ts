
// src/api/session.ts
import { HttpClient } from './http-client';

export interface SessionResponse {
  success: boolean;
  sessionId: string;
  isNew?: boolean;
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
  
  constructor(client: HttpClient) {
    this.client = client;
  }
  
  async createSession(): Promise<SessionResponse> {
    return this.client.post<SessionResponse>('/sessions/', {});
  }
  
  async getSession(sessionId: string): Promise<SessionResponse> {
    return this.client.get<SessionResponse>(`/sessions/get?sessionId=${sessionId}`);
  }
  
  async keepAlive(sessionId: string): Promise<{ success: boolean }> {
    return this.client.post<{ success: boolean }>('/sessions/keep-alive', { sessionId });
  }
  
  async getSessionState(sessionId: string): Promise<SessionStateResponse> {
    return this.client.get<SessionStateResponse>(`/sessions/state?sessionId=${sessionId}`);
  }
  
  async reconnectSession(sessionId: string, reconnectAttempt: number): Promise<SessionResponse> {
    return this.client.post<SessionResponse>('/sessions/reconnect', { 
      sessionId, 
      reconnectAttempt 
    });
  }
  
  async updateConnectionQuality(
    sessionId: string, 
    latencyMs: number, 
    missedHeartbeats: number, 
    connectionType: string
  ): Promise<{ quality: string; reconnectRecommended: boolean }> {
    return this.client.post<{ quality: string; reconnectRecommended: boolean }>(
      '/sessions/connection-quality', 
      { sessionId, latencyMs, missedHeartbeats, connectionType }
    );
  }
}
