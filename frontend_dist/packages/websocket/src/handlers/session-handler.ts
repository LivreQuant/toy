// src/handlers/session-handler.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';

import { SocketClient } from '../client/socket-client';
import { 
  ClientSessionInfoRequest,
  ClientStopSessionRequest,
  ServerSessionInfoResponse,
  ServerStopSessionResponse 
} from '../types/message-types';

export class SessionHandler {
  private logger = getLogger('SessionHandler');
  private responseTimeoutMs = 15000;
  
  constructor(private client: SocketClient) {
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
      
      this.logger.info('Session info response received', response);
      
      return {
        ...response,
        success: true,
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

  private async sendRequest<T>(
    message: any, 
    predicate: (message: any) => boolean
  ): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const timeoutId = window.setTimeout(() => {
        subscription.unsubscribe();
        reject(new Error(`Request timed out after ${this.responseTimeoutMs}ms`));
      }, this.responseTimeoutMs);
      
      const subscription = this.client.on('message', (msg) => {
        if (predicate(msg)) {
          window.clearTimeout(timeoutId);
          subscription.unsubscribe();
          resolve(msg as T);
        }
      });
      
      if (!this.client.send(message)) {
        window.clearTimeout(timeoutId);
        subscription.unsubscribe();
        reject(new Error('Failed to send request: client not connected'));
      }
    });
  }
}