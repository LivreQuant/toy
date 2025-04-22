// src/services/websocket/message-handlers/simulator.ts
import { getLogger } from '../../../boot/logging';
import { SocketClient } from '../../connection/socket-client';
import { DeviceIdManager } from '../../auth/device-id-manager';
import { 
  ClientStartSimulatorMessage,
  ClientStopSimulatorMessage,
  ServerSimulatorStartedResponse,
  ServerSimulatorStoppedResponse 
} from '../message-types';

export class SimulatorHandler {
  private logger = getLogger('SimulatorHandler');
  private client: SocketClient;
  private responseTimeoutMs = 15000;
  
  constructor(client: SocketClient) {
    this.client = client;
    this.logger.info('SimulatorHandler initialized');
  }

  /**
   * Starts the simulator
   */
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

  /**
   * Stops the simulator
   */
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