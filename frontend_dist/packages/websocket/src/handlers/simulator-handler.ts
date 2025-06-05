// src/handlers/simulator-handler.ts
import { getLogger } from '@trading-app/logging';
import { DeviceIdManager } from '@trading-app/auth';

import { SocketClient } from '../client/socket-client';
import { 
  ClientStartSimulatorMessage,
  ClientStopSimulatorMessage,
  ServerSimulatorStartedResponse,
  ServerSimulatorStoppedResponse 
} from '../types/message-types';

export class SimulatorHandler {
  private logger = getLogger('SimulatorHandler');
  private responseTimeoutMs = 15000;
  
  constructor(private client: SocketClient) {
    this.logger.info('SimulatorHandler initialized');
  }

  public async startSimulator(): Promise<ServerSimulatorStartedResponse> {
    this.logger.info('Requesting simulator start');
    
    const requestId = `start-simulator-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    const message: ClientStartSimulatorMessage = {
      type: 'start_simulator',
      requestId,
      timestamp: Date.now(),
      deviceId: DeviceIdManager.getInstance().getDeviceId()
    };
    
    return this.sendRequest<ServerSimulatorStartedResponse>(
      message, 
      (msg) => msg.type === 'simulator_started' && msg.requestId === requestId
    );
  }

  public async stopSimulator(): Promise<ServerSimulatorStoppedResponse> {
    this.logger.info('Requesting simulator stop');
    
    const requestId = `stop-simulator-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    const message: ClientStopSimulatorMessage = {
      type: 'stop_simulator',
      requestId,
      timestamp: Date.now(),
      deviceId: DeviceIdManager.getInstance().getDeviceId()
    };
    
    return this.sendRequest<ServerSimulatorStoppedResponse>(
      message, 
      (msg) => msg.type === 'simulator_stopped' && msg.requestId === requestId
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