// src/api/session.ts
import { HttpClient } from './http-client';
import { TokenManager } from '../services/auth/token-manager';

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
  async createOrGetSession(): Promise<SessionResponse> {
    return this.client.post<SessionResponse>('/sessions');
  }
  
  // Get current session state 
  async getSessionState(): Promise<SessionStateResponse> {
    return this.client.get<SessionStateResponse>('/sessions');
  }
}