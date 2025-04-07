// src/api/auth.ts
import { HttpClient } from './http-client';

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
    return this.client.post<LoginResponse>(
      '/auth/login',
      { username, password },
      { skipAuth: true }
    );
  }

  async logout(): Promise<void> {
    return this.client.post<void>('/auth/logout');
  }

  async refreshToken(refreshToken: string): Promise<LoginResponse> {
    // Include deviceId during token refresh
    return this.client.post<LoginResponse>(
      '/auth/refresh',
      { refreshToken },
      { skipAuth: true }
    );
  }
}