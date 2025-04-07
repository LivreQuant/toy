// src/api/session.ts
import { HttpClient } from './http-client';
// Removed SessionManager import as getDeviceId is static on DeviceIdManager
import { DeviceIdManager } from '../utils/device-id-manager';

// Interfaces remain the same
export interface SessionResponse {
  success: boolean;
  errorMessage?: string;
}

export interface SessionStateResponse {
  success: boolean;
  simulatorStatus: string; // Consider using a specific enum if possible
  sessionCreatedAt: number; // Timestamp
  lastActive: number; // Timestamp
}

/**
 * API client for interacting with the backend session endpoints.
 */
export class SessionApi {
  private client: HttpClient;

  constructor(client: HttpClient) {
    this.client = client;
  }

  /**
   * Creates a new session or validates an existing one on the backend.
   * Includes the current device ID in the request.
   * @returns A promise resolving to a SessionResponse.
   */
  async createSession(): Promise<SessionResponse> {
    // Use the static method from DeviceIdManager
    const deviceId = DeviceIdManager.getInstance().getDeviceId();
    return this.client.post<SessionResponse>('/sessions', {
      deviceId // Send deviceId in the request body
    });
  }

  /**
   * Deletes the current session on the backend.
   * The specific session is typically identified by backend mechanisms (e.g., cookies, tokens).
   * @returns A promise resolving to a SessionResponse.
   */
  async deleteSession(): Promise<SessionResponse> {
    // Sending an empty object {} might not be necessary for DELETE if no body is expected.
    // Adjust based on your API definition.
    return this.client.delete<SessionResponse>('/sessions'); // Pass options if needed, e.g., {}
  }

  // Optional: Method to get session state if your backend provides it
  // async getSessionState(): Promise<SessionStateResponse> {
  //   return this.client.get<SessionStateResponse>('/sessions/state');
  // }
}