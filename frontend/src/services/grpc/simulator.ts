// src/services/grpc/simulator.ts
import { grpc } from '@improbable-eng/grpc-web';
import { SimulatorManagerService } from '../../generated/simulator_manager_pb_service';
import { 
  StartSimulatorRequest, StartSimulatorResponse,
  StopSimulatorRequest, StopSimulatorResponse,
  GetSimulatorStatusRequest, GetSimulatorStatusResponse
} from '../../generated/simulator_manager_pb';
import { SimulatorStatus } from '../../types/simulator';

const host = 'http://localhost:8080';

export const startSimulator = (token: string, sessionId: string): Promise<{
  success: boolean;
  simulatorId: string;
  simulatorEndpoint: string;
  errorMessage?: string;
}> => {
  return new Promise((resolve, reject) => {
    const request = new StartSimulatorRequest();
    request.setToken(token);
    request.setSessionId(sessionId);
    
    grpc.unary(SimulatorManagerService.StartSimulator, {
      request,
      host,
      onEnd: (response) => {
        const { status, statusMessage, message } = response;
        
        if (status === grpc.Code.OK && message) {
          const startResponse = message as StartSimulatorResponse;
          resolve({
            success: startResponse.getSuccess(),
            simulatorId: startResponse.getSimulatorId(),
            simulatorEndpoint: startResponse.getSimulatorEndpoint(),
            errorMessage: startResponse.getErrorMessage()
          });
        } else {
          reject(new Error(statusMessage || 'Unknown error'));
        }
      }
    });
  });
};

export const stopSimulator = (token: string, simulatorId: string): Promise<{
  success: boolean;
  errorMessage?: string;
}> => {
  return new Promise((resolve, reject) => {
    const request = new StopSimulatorRequest();
    request.setToken(token);
    request.setSimulatorId(simulatorId);
    
    grpc.unary(SimulatorManagerService.StopSimulator, {
      request,
      host,
      onEnd: (response) => {
        const { status, statusMessage, message } = response;
        
        if (status === grpc.Code.OK && message) {
          const stopResponse = message as StopSimulatorResponse;
          resolve({
            success: stopResponse.getSuccess(),
            errorMessage: stopResponse.getErrorMessage()
          });
        } else {
          reject(new Error(statusMessage || 'Unknown error'));
        }
      }
    });
  });
};

export const getSimulatorStatus = (token: string, simulatorId: string): Promise<{
  status: SimulatorStatus;
  errorMessage?: string;
}> => {
  return new Promise((resolve, reject) => {
    const request = new GetSimulatorStatusRequest();
    request.setToken(token);
    request.setSimulatorId(simulatorId);
    
    grpc.unary(SimulatorManagerService.GetSimulatorStatus, {
      request,
      host,
      onEnd: (response) => {
        const { status, statusMessage, message } = response;
        
        if (status === grpc.Code.OK && message) {
          const statusResponse = message as GetSimulatorStatusResponse;
          
          // Map the protobuf enum to our type
          const statusMap: Record<number, SimulatorStatus> = {
            0: 'UNKNOWN',
            1: 'STARTING',
            2: 'RUNNING',
            3: 'STOPPING',
            4: 'STOPPED',
            5: 'ERROR'
          };
          
          resolve({
            status: statusMap[statusResponse.getStatus()] || 'UNKNOWN',
            errorMessage: statusResponse.getErrorMessage()
          });
        } else {
          reject(new Error(statusMessage || 'Unknown error'));
        }
      }
    });
  });
};