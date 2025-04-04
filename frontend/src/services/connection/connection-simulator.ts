// src/services/connection/connection-simulator.ts
import { SimulatorApi } from '../../api/simulator';
import { HttpClient } from '../../api/http-client';

export class ConnectionSimulatorManager {
  private simulatorApi: SimulatorApi;

  constructor(httpClient: HttpClient) {
    this.simulatorApi = new SimulatorApi(httpClient);
  }

  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    try {
      const response = await this.simulatorApi.startSimulator();
      
      return { 
        success: response.success,
        status: response.status
      };
    } catch (error) {
      console.error('Failed to start simulator:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Simulator start failed' 
      };
    }
  }

  public async stopSimulator(): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await this.simulatorApi.stopSimulator();
      
      return { success: response.success };
    } catch (error) {
      console.error('Failed to stop simulator:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Simulator stop failed' 
      };
    }
  }
}