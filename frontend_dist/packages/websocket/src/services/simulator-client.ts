// src/services/simulator-client.ts
import { getLogger } from '@trading-app/logging';
import { handleError } from '@trading-app/utils';

import { SocketClient } from '../client/socket-client';
import { SimulatorHandler } from '../handlers/simulator-handler';
import { StateManager } from '../types/connection-types';

export class SimulatorClient {
  private logger = getLogger('SimulatorClient');
  private socketClient: SocketClient;
  private simulatorHandler: SimulatorHandler;
  
  constructor(socketClient: SocketClient, private stateManager: StateManager) {
    this.socketClient = socketClient;
    this.simulatorHandler = new SimulatorHandler(socketClient);
    this.logger.info('SimulatorClient initialized');
  }

  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    this.logger.info('Starting simulator...');
    
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
        error: error.message
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
    this.logger.info('Stopping simulator...');
    
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
        error: error.message
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