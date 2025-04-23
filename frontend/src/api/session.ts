// src/api/session.ts
import { ConnectionManager } from '../services/connection/connection-manager';

export interface SessionResponse {
  success: boolean;
  errorMessage?: string;
}

export interface SessionStateResponse {
  success: boolean;
  simulatorStatus: string;
  sessionCreatedAt: number;
  lastActive: number;
}

/**
 * API client for interacting with the backend session endpoints via WebSocket.
 */
export class SessionApi {
  private connectionManager: ConnectionManager;

  constructor(connectionManager: ConnectionManager) {
    this.connectionManager = connectionManager;
  }

  /**
   * Creates a new session or validates an existing one on the backend.
   * @returns A promise resolving to a SessionResponse.
   */
  async createSession(): Promise<SessionResponse> {
    try {
      const response = await this.connectionManager.createSession();
      console.log("CRITICAL DEBUG: Session validation response:", response);
      
      // Explicitly check for valid session conditions
      const isSessionValid = 
        response.sessionId && 
        response.userId && 
        response.status === "ACTIVE" && 
        response.expiresAt > (Date.now() / 1000);
  
      return {
        success: true,
        errorMessage: isSessionValid ? undefined : 'Invalid session'
      };
    } catch (error: any) {
      console.log("CRITICAL DEBUG: Session validation error:", error);
      return {
        success: false,
        errorMessage: error.message || 'Failed to create session via WebSocket'
      };
    }
  }

  /**
   * Deletes the current session on the backend.
   * @returns A promise resolving to a SessionResponse.
   */
  async deleteSession(): Promise<SessionResponse> {
    try {
      // Use ConnectionManager's disconnect method
      const result = await this.connectionManager.disconnect('user_logout');
      return {
        success: result,
        errorMessage: result ? undefined : 'Failed to delete session'
      };
    } catch (error: any) {
      return {
        success: false,
        errorMessage: error.message || 'Failed to delete session'
      };
    }
  }
}