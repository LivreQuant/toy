// src/services/connection/connection-simulator.ts
import { SimulatorApi, SimulatorStatusResponse } from '../../api/simulator'; // Import type
import { HttpClient } from '../../api/http-client';
import { getLogger } from '../../boot/logging'; // Use logger
import { AppErrorHandler } from '../../utils/app-error-handler';
import { ErrorSeverity } from '../../utils/error-handler';

const logger = getLogger('ConnectionSimulatorManager');

export class ConnectionSimulatorManager {
  private simulatorApi: SimulatorApi;

  constructor(httpClient: HttpClient) {
    this.simulatorApi = new SimulatorApi(httpClient);
    logger.info('ConnectionSimulatorManager initialized');
  }

  /**
   * Calls the API to start the simulator.
   * Handles errors via AppErrorHandler.
   * @returns A promise resolving to the API response structure.
   */
  public async startSimulator(): Promise<SimulatorStatusResponse> {
    logger.info('Requesting to start simulator...');
    try {
      const response = await this.simulatorApi.startSimulator();
      if (response.success) {
        logger.info(`Simulator start request successful, status: ${response.status}`);
      } else {
        logger.warn(`Simulator start request failed via API: ${response.errorMessage}`);
        // Let ConnectionManager handle AppErrorHandler notification based on context
      }
      return response;
    } catch (error: any) {
      logger.error('Exception while trying to start simulator', { error: error.message });
      const errorMsg = `Failed to send start simulator request: ${error.message}`;
      // Let ConnectionManager handle AppErrorHandler notification
      // AppErrorHandler.handleConnectionError(error, ErrorSeverity.HIGH, 'StartSimulatorException');
      // Re-throw or return a failure structure
      return { success: false, status: 'ERROR', errorMessage: errorMsg };
    }
  }

  /**
   * Calls the API to stop the simulator.
   * Handles errors via AppErrorHandler.
   * @returns A promise resolving to the API response structure.
   */
  public async stopSimulator(): Promise<SimulatorStatusResponse> {
    logger.info('Requesting to stop simulator...');
    try {
      // Assuming stop might return a status response similar to start
      const response = await this.simulatorApi.stopSimulator();
      if (response.success) {
         logger.info(`Simulator stop request successful, status: ${response.status}`);
      } else {
         logger.warn(`Simulator stop request failed via API: ${response.errorMessage}`);
          // Let ConnectionManager handle AppErrorHandler notification
      }
      return response;
    } catch (error: any) {
      logger.error('Exception while trying to stop simulator', { error: error.message });
       const errorMsg = `Failed to send stop simulator request: ${error.message}`;
       // Let ConnectionManager handle AppErrorHandler notification
      // AppErrorHandler.handleConnectionError(error, ErrorSeverity.HIGH, 'StopSimulatorException');
      // Re-throw or return a failure structure
       return { success: false, status: 'ERROR', errorMessage: errorMsg };
    }
  }

   // Optional: Method to get simulator status periodically?
   // public async getSimulatorStatus(): Promise<SimulatorStatusResponse> { ... }
}