
// src/api/session.ts
import { HttpClient } from './http-client';
import { TokenManager } from '../services/auth/token-manager';


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

export interface SessionReadyResponse {
  success: boolean;
  status: string;
  message?: string;
}

export class SessionApi {
  private client: HttpClient;
  private tokenManager: TokenManager;  // Add this property
  
  constructor(client: HttpClient, tokenManager: TokenManager) {  // Update constructor
    this.client = client;
    this.tokenManager = tokenManager;  // Store the token manager
  }

  async createSession(): Promise<SessionResponse> {
    // Get token from tokenManager
    const token = await this.tokenManager.getAccessToken();
    
    // Get user ID (you might need to store this after login)
    const userId = localStorage.getItem('user_id'); 
    
    return this.client.post<SessionResponse>('/sessions', {
      userId: userId,
      token: token
    });
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

  // Add this new method
  async checkSessionReady(sessionId: string): Promise<SessionReadyResponse> {
    const token = await this.tokenManager.getAccessToken();
    
    return this.client.get<SessionReadyResponse>(`/sessions/${sessionId}/ready?token=${token}`);
  }
}
