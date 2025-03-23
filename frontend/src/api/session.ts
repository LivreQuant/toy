// src/api/session.ts
import { HttpClient } from './http-client';

export interface SessionResponse {
  success: boolean;
  sessionId: string;
  podName?: string;
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
    return this.client.post<SessionResponse>('/session/create');
  }
  
  async getSession(sessionId: string): Promise<SessionResponse> {
    return this.client.get<SessionResponse>(`/session/get?sessionId=${sessionId}`);
  }
  
  async keepAlive(sessionId: string): Promise<{ success: boolean }> {
    return this.client.post<{ success: boolean }>('/session/keep-alive', { sessionId });
  }
  
  async getSessionState(sessionId: string): Promise<SessionStateResponse> {
    return this.client.get<SessionStateResponse>(`/session/state?sessionId=${sessionId}`);
  }
  
  async reconnectSession(sessionId: string, reconnectAttempt: number): Promise<SessionResponse> {
    return this.client.post<SessionResponse>('/session/reconnect', { 
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
      '/session/connection-quality', 
      { sessionId, latencyMs, missedHeartbeats, connectionType }
    );
  }
}