// src/services/connection/connection-simulator.ts
import { HttpClient } from '../../api/http-client';

export class ConnectionSimulatorManager {
  private httpClient: HttpClient;

  constructor(httpClient: HttpClient) {
    this.httpClient = httpClient;
  }

  public async startSimulator(): Promise<{ success: boolean; status?: string; error?: string }> {
    try {
      const response = await this.httpClient.post<{success: boolean, status?: string}>('/simulators');
      
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
      const response = await this.httpClient.delete<{success: boolean}>('/simulators');
      
      return { success: response.success };
    } catch (error) {
      console.error('Failed to stop simulator:', error);
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Simulator stop failed' 
      };
    }
  }

  public async getSimulatorStatus(): Promise<{ success: boolean; status: string; error?: string }> {
    try {
      const response = await this.httpClient.get<{success: boolean, status: string}>('/simulators');
      
      return { 
        success: response.success,
        status: response.status
      };
    } catch (error) {
      console.error('Failed to get simulator status:', error);
      return { 
        success: false, 
        status: 'ERROR',
        error: error instanceof Error ? error.message : 'Failed to retrieve simulator status' 
      };
    }
  }
}