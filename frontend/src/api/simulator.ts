// src/api/simulator.ts
import { ConnectionManager } from '../services/connection/connection-manager';

export interface SimulatorStatusResponse {
  success: boolean;
  status: string;
  uptime?: number;
  errorMessage?: string;
}

/**
 * API client for interacting with the simulator via WebSocket.
 */
export class SimulatorApi {
  
  constructor(connectionManager: ConnectionManager) {
    this.connectionManager = connectionManager;
  }

  /**
   * Starts the simulator.
   * @returns A promise resolving to a SimulatorStatusResponse.
   */
  async startSimulator(): Promise<SimulatorStatusResponse> {
    try {
      // Using WebSocket to start simulator
      const response = await this.wsManager.startSimulator();
      return {
        success: response.success,
        status: response.status || 'UNKNOWN',
        errorMessage: response.error
      };
    } catch (error: any) {
      return {
        success: false,
        status: 'ERROR',
        errorMessage: error.message || 'Failed to start simulator via WebSocket'
      };
    }
  }

  /**
   * Stops the simulator.
   * @returns A promise resolving to a SimulatorStatusResponse.
   */
  async stopSimulator(): Promise<SimulatorStatusResponse> {
    try {
      // Using WebSocket to stop simulator
      const response = await this.wsManager.stopSimulator();
      return {
        success: response.success,
        status: 'STOPPED', // Assume STOPPED on success
        errorMessage: response.error
      };
    } catch (error: any) {
      return {
        success: false,
        status: 'ERROR',
        errorMessage: error.message || 'Failed to stop simulator via WebSocket'
      };
    }
  }
}