// src/api/auth.ts
import { HttpClient } from './http-client';
import { SessionManager } from '../services/session/session-manager';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  userId: number;
}

export class AuthApi {
  private client: HttpClient;
  
  constructor(client: HttpClient) {
    this.client = client;
  }
  
  async login(username: string, password: string): Promise<LoginResponse> {
    // Include deviceId during login
    const deviceId = SessionManager.getDeviceId();
    return this.client.post<LoginResponse>(
      '/auth/login', 
      { username, password, deviceId }, 
      { skipAuth: true }
    );
  }
  
  async logout(): Promise<void> {
    return this.client.post<void>('/auth/logout');
  }
  
  async refreshToken(refreshToken: string): Promise<LoginResponse> {
    // Include deviceId during token refresh
    const deviceId = SessionManager.getDeviceId();
    return this.client.post<LoginResponse>(
      '/auth/refresh', 
      { refreshToken, deviceId }, 
      { skipAuth: true }
    );
  }
}