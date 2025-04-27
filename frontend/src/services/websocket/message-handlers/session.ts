// src/services/websocket/message-handlers/session.ts
import { getLogger } from '../../../boot/logging';

import { SocketClient } from '../../connection/socket-client';

import { DeviceIdManager } from '../../auth/device-id-manager';

import { 
  ClientSessionInfoRequest,
  ClientStopSessionRequest,
  ServerSessionInfoResponse,
  ServerStopSessionResponse 
} from '../message-types';

export class SessionHandler {
  private logger = getLogger('SessionHandler');
  private client: SocketClient;
  private responseTimeoutMs = 15000;
  
  constructor(client: SocketClient) {
      this.client = client;
      this.logger.info('SessionHandler initialized');
  }
  
  public async requestSessionInfo(): Promise<ServerSessionInfoResponse> {
    this.logger.info('Requesting session information');
    
    const requestId = `session-info-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    const message: ClientSessionInfoRequest = {
        type: 'request_session',
        requestId,
        timestamp: Date.now(),
        deviceId: DeviceIdManager.getInstance().getDeviceId()
    };
    
    try {
        const response = await this.sendRequest<ServerSessionInfoResponse>(
            message, 
            (msg) => msg.type === 'session_info' && msg.requestId === requestId
        );
        
        // Log the full response for debugging
        this.logger.info('Session info response received', response);
        
        // Return the response as-is, with type casting if needed
        // If we're missing properties, either add them with default values
        // or use a type assertion to tell TypeScript it's correct
        return {
            ...response,
            success: true, // Add explicit success flag if backend doesn't provide it
            // Add any missing required properties with default values
            sessionId: response.sessionId || 'unknown',
            userId: response.userId || 'unknown',
            status: response.status || 'active',
            createdAt: response.createdAt || Date.now(),
            simulatorId: response.simulatorId || null
        } as ServerSessionInfoResponse;
    } catch (error: any) {
        this.logger.error('Error requesting session info', {
            error: error instanceof Error ? error.message : String(error)
        });
        throw error;
    }
  }

  /**
   * Stops the current session
   */
  public async stopSession(): Promise<ServerStopSessionResponse> {
    this.logger.info('Requesting session stop');
    
    const requestId = `stop-session-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    const message: ClientStopSessionRequest = {
      type: 'stop_session',
      requestId,
      timestamp: Date.now(),
      deviceId: DeviceIdManager.getInstance().getDeviceId()
    };
    
    return this.sendRequest<ServerStopSessionResponse>(
      message, 
      (msg) => msg.type === 'session_stopped' && msg.requestId === requestId
    );
  }

  /**
   * Generic method to send a request and wait for a response
   */
  private async sendRequest<T>(
    message: any, 
    predicate: (message: any) => boolean
  ): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      // Create timeout to handle unresponsive server
      const timeoutId = window.setTimeout(() => {
        subscription.unsubscribe();
        reject(new Error(`Request timed out after ${this.responseTimeoutMs}ms`));
      }, this.responseTimeoutMs);
      
      // Listen for response
      const subscription = this.client.on('message', (msg) => {
        if (predicate(msg)) {
          window.clearTimeout(timeoutId);
          subscription.unsubscribe();
          resolve(msg as T);
        }
      });
      
      // Send the request
      if (!this.client.send(message)) {
        window.clearTimeout(timeoutId);
        subscription.unsubscribe();
        reject(new Error('Failed to send request: client not connected'));
      }
    });
  }
}