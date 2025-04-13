// src/services/connection/connection-simulator.ts
import { SimulatorApi, SimulatorStatusResponse } from '../../api/simulator';
import { WebSocketManager } from '../../services/websocket/websocket-manager'; // Fixed path
import { getLogger } from '../../boot/logging';

const logger = getLogger('ConnectionSimulatorManager');

export class ConnectionSimulatorManager {
  private wsManager: WebSocketManager;
  private simulatorApi: SimulatorApi;

  constructor(wsManager: WebSocketManager) {
    this.wsManager = wsManager;
    this.simulatorApi = new SimulatorApi(wsManager);
    logger.info('ConnectionSimulatorManager initialized');
  }

  public async startSimulator(): Promise<SimulatorStatusResponse> {
    logger.info('Requesting to start simulator...');
    try {
      const response = await this.wsManager.startSimulator();
      if (response.success) {
        logger.info(`Simulator start request successful, status: ${response.status}`);
      } else {
        logger.warn(`Simulator start request failed via API: ${response.error}`);
      }
      return {
        success: response.success,
        status: response.status || 'UNKNOWN',
        errorMessage: response.error
      };
    } catch (error: any) {
      logger.error('Exception while trying to start simulator', { error: error.message });
      const errorMsg = `Failed to send start simulator request: ${error.message}`;
      return { success: false, status: 'ERROR', errorMessage: errorMsg };
    }
  }

  public async stopSimulator(): Promise<SimulatorStatusResponse> {
    logger.info('Requesting to stop simulator...');
    try {
      const response = await this.wsManager.stopSimulator();
      if (response.success) {
         logger.info(`Simulator stop request successful`);
      } else {
         logger.warn(`Simulator stop request failed via API: ${response.error}`);
      }
      return {
        success: response.success,
        status: 'STOPPED',
        errorMessage: response.error
      };
    } catch (error: any) {
      logger.error('Exception while trying to stop simulator', { error: error.message });
       const errorMsg = `Failed to send stop simulator request: ${error.message}`;
       return { success: false, status: 'ERROR', errorMessage: errorMsg };
    }
  }
}