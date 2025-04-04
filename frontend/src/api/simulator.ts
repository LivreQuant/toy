// src/api/simulator.ts
import { HttpClient } from './http-client';

export interface StartSimulatorRequest {
  initialSymbols?: string[];
  initialCash?: number;
}

export interface SimulatorStatusResponse {
  success: boolean;
  status: string;
  simulatorId?: string;
  uptime?: number;
  errorMessage?: string;
}

export class SimulatorApi {
  private client: HttpClient;
  
  constructor(client: HttpClient) {
    this.client = client;
  }
  
  async startSimulator(request: StartSimulatorRequest = {}): Promise<SimulatorStatusResponse> {
    return this.client.post<SimulatorStatusResponse>('/simulators', request);
  }
  
  async stopSimulator(): Promise<SimulatorStatusResponse> {
    return this.client.delete<SimulatorStatusResponse>('/simulators');
  }
}