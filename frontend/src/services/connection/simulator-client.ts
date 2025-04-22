// src/services/connection/simulator-client.ts
import { getLogger } from '../../boot/logging';
import { SocketClient } from './socket-client';
import { SimulatorHandler } from '../websocket/message-handlers/simulator';
import { simulatorState } from '../../state/simulator-state';
import { handleError } from '../../utils/error-handling';

export class SimulatorClient {
  private logger = getLogger('SimulatorClient');
  private socketClient: SocketClient;
  private simulatorHandler: SimulatorHandler;
  
  constructor(socketClient: SocketClient) {
    this.socketClient = socketClient;
    this.simulatorHandler = new SimulatorHandler(socketClient);
    this.logger.info('SimulatorClient initialized');
  }

  /**
   * Starts the simulator.
   * @returns A promise resolving to the start result.
   */
  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    this.logger.info('Starting simulator...');
    
    simulatorState.updateState({
      status: 'STARTING',
      isLoading: true,
      error: null
    });
    
    try {
      const response = await this.simulatorHandler.startSimulator();
      
      if (response.success) {
        this.logger.info(`Simulator start request successful, status: ${response.status}`);
        simulatorState.setStatus(response.status as any || 'RUNNING');
      } else {
        this.logger.warn(`Simulator start request failed: ${response.error}`);
        simulatorState.setStatus('ERROR', response.error);
        
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
        error: error.message
      });
      
      simulatorState.setStatus('ERROR', error.message);
      
      return handleError(
        error instanceof Error ? error.message : String(error || 'Failed to start simulator'),
        'StartSimulatorException',
        'high'
      );
    }
  }

  /**
   * Stops the simulator.
   * @returns A promise resolving to the stop result.
   */
  public async stopSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    this.logger.info('Stopping simulator...');
    
    simulatorState.updateState({
      status: 'STOPPING',
      isLoading: true,
      error: null
    });
    
    try {
      const response = await this.simulatorHandler.stopSimulator();
      
      if (response.success) {
        this.logger.info('Simulator stop request successful');
        simulatorState.setStatus('STOPPED');
      } else {
        this.logger.warn(`Simulator stop request failed: ${response.error}`);
        simulatorState.setStatus('ERROR', response.error);
        
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
        error: error.message
      });
      
      simulatorState.setStatus('ERROR', error.message);
      
      return handleError(
        error instanceof Error ? error.message : String(error || 'Failed to stop simulator'),
        'StopSimulatorException',
        'high'
      );
    }
  }
}