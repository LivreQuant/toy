// frontend_dist/packages/websocket/src/services/simulator-client.ts
import { getLogger } from '@trading-app/logging';
import { handleError } from '@trading-app/utils';

import { SocketClient } from '../client/socket-client';
import { SimulatorHandler } from '../handlers/simulator-handler';
import { StateManager } from '../types/connection-types';

export class SimulatorClient {
  private logger = getLogger('SimulatorClient');
  private simulatorHandler: SimulatorHandler;
  
  constructor(
    private socketClient: SocketClient, // ✅ Receive the shared instance
    private stateManager: StateManager
  ) {
    // 🚨 FIX: Use the passed socketClient instead of creating new one
    this.simulatorHandler = new SimulatorHandler(this.socketClient); // ✅ Use shared instance
    
    this.logger.info('SimulatorClient initialized with shared SocketClient', {
      hasSocketClient: !!this.socketClient,
      socketClientSocket: (this.socketClient as any).socket,
      simulatorHandlerClient: (this.simulatorHandler as any).client
    });
  }

  // 🚨 NEW: Public getter for debugging
  public getSocketClient(): SocketClient {
    return this.socketClient;
  }

  // 🚨 NEW: Debug method
  public debugSocketClient(): void {
    console.log('🔍 SIMULATOR CLIENT DEBUG:', {
      socketClient: this.socketClient,
      socketClientInfo: this.socketClient.getSocketInfo(), // ✅ Use public getter
      simulatorHandler: this.simulatorHandler,
      simulatorHandlerClient: (this.simulatorHandler as any).client,
      instancesMatch: this.socketClient === (this.simulatorHandler as any).client
    });
  }

  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    // 🚨 FIXED: Use public getter instead of private property
    this.logger.info('Starting simulator...', {
      socketClientInfo: this.socketClient.getSocketInfo(), // ✅ Use public getter
      socketClientStatus: this.socketClient.getCurrentStatus()
    });
    
    this.stateManager.updateSimulatorState({
      status: 'STARTING',
      isLoading: true,
      error: null
    });
    
    try {
      const response = await this.simulatorHandler.startSimulator();
      
      if (response.success) {
        this.logger.info(`Simulator start request successful, status: ${response.status}`);
        this.stateManager.updateSimulatorState({
          status: response.status || 'RUNNING',
          isLoading: false,
          error: null
        });
      } else {
        this.logger.warn(`Simulator start request failed: ${response.error}`);
        this.stateManager.updateSimulatorState({
          status: 'ERROR',
          isLoading: false,
          error: response.error
        });
        
        return handleError(
          response.error || 'Failed to start simulator',
          'StartSimulatorFailure',
          'medium'
        );
      }
      
      return {
        success: response.success,
        status: response.status,
        error: response.error
      };
    } catch (error: any) {
      this.logger.error('Exception while trying to start simulator', {
        error: error.message,
        socketClientHasSocket: !!(this.socketClient as any).socket,
        socketClientStatus: this.socketClient.getCurrentStatus()
      });
      
      this.stateManager.updateSimulatorState({
        status: 'ERROR',
        isLoading: false,
        error: error.message
      });
      
      return handleError(
        error instanceof Error ? error.message : String(error || 'Failed to start simulator'),
        'StartSimulatorException',
        'high'
      );
    }
  }

  public async stopSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    // 🚨 FIXED: Use public getter instead of private property
    this.logger.info('Stopping simulator...', {
      socketClientInfo: this.socketClient.getSocketInfo(), // ✅ Use public getter
      socketClientStatus: this.socketClient.getCurrentStatus()
    });
    
    this.stateManager.updateSimulatorState({
      status: 'STOPPING',
      isLoading: true,
      error: null
    });
    
    try {
      const response = await this.simulatorHandler.stopSimulator();
      
      if (response.success) {
        this.logger.info('Simulator stop request successful');
        this.stateManager.updateSimulatorState({
          status: 'STOPPED',
          isLoading: false,
          error: null
        });
      } else {
        this.logger.warn(`Simulator stop request failed: ${response.error}`);
       this.stateManager.updateSimulatorState({
         status: 'ERROR',
         isLoading: false,
         error: response.error
       });
       
       return handleError(
         response.error || 'Failed to stop simulator',
         'StopSimulatorFailure',
         'medium'
       );
     }
     
     return {
       success: response.success,
       error: response.error
     };
   } catch (error: any) {
     this.logger.error('Exception while trying to stop simulator', {
       error: error.message,
       socketClientHasSocket: !!(this.socketClient as any).socket,
       socketClientStatus: this.socketClient.getCurrentStatus()
     });
     
     this.stateManager.updateSimulatorState({
       status: 'ERROR',
       isLoading: false,
       error: error.message
     });
     
     return handleError(
       error instanceof Error ? error.message : String(error || 'Failed to stop simulator'),
       'StopSimulatorException',
       'high'
     );
   }
 }
}