// src/api/simulator.ts
import { HttpClient } from './http-client';

export interface SimulatorStatusResponse {
  success: boolean;
  status: string;
  uptime?: number;
  errorMessage?: string;
}

export class SimulatorApi {
  private client: HttpClient;
  
  constructor(client: HttpClient) {
    this.client = client;
  }
  
  async startSimulator(): Promise<SimulatorStatusResponse> {
    return this.client.get<SimulatorStatusResponse>('/simulators');
  }
  
  async stopSimulator(): Promise<SimulatorStatusResponse> {
    return this.client.delete<SimulatorStatusResponse>('/simulators');
  }
}