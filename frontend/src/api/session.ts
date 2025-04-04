// src/api/session.ts
import { HttpClient } from './http-client';
import { SessionManager } from '../services/session/session-manager';

export interface SessionResponse {
  success: boolean;
  sessionId: string;
  errorMessage?: string;
}

export interface SessionStateResponse {
  success: boolean;
  simulatorId: string;
  simulatorStatus: string;
  sessionCreatedAt: number;
  lastActive: number;
}

export class SessionApi {
  private client: HttpClient;
  
  constructor(client: HttpClient) {
    this.client = client;
  }

  // Create a new session or get the existing one
  async createSession(userId: string | number): Promise<SessionResponse> {
    const deviceId = SessionManager.getDeviceId();
    return this.client.post<SessionResponse>('/sessions', { 
      deviceId 
    });
  }

  // Delte an existing session
  async deleteSession(userId: string | number): Promise<SessionResponse> {
    return this.client.delete<SessionResponse>('/sessions', {});
  }
}