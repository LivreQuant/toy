// src/services/grpc/session.ts
import { grpc } from '@improbable-eng/grpc-web';
import { SessionManagerService } from '../../generated/session_manager_pb_service';
import { 
  CreateSessionRequest, CreateSessionResponse,
  GetSessionRequest, GetSessionResponse,
  EndSessionRequest, EndSessionResponse,
  KeepAliveRequest, KeepAliveResponse
} from '../../generated/session_manager_pb';

const host = 'http://localhost:8080';

export const createSession = (token: string): Promise<{
  success: boolean;
  sessionId: string;
  errorMessage?: string;
}> => {
  return new Promise((resolve, reject) => {
    const request = new CreateSessionRequest();
    request.setToken(token);
    
    grpc.unary(SessionManagerService.CreateSession, {
      request,
      host,
      onEnd: (response) => {
        const { status, statusMessage, message } = response;
        
        if (status === grpc.Code.OK && message) {
          const createResponse = message as CreateSessionResponse;
          resolve({
            success: createResponse.getSuccess(),
            sessionId: createResponse.getSessionId(),
            errorMessage: createResponse.getErrorMessage()
          });
        } else {
          reject(new Error(statusMessage || 'Unknown error'));
        }
      }
    });
  });
};

export const getSession = (token: string, sessionId: string): Promise<{
  sessionActive: boolean;
  simulatorEndpoint?: string;
  errorMessage?: string;
}> => {
  return new Promise((resolve, reject) => {
    const request = new GetSessionRequest();
    request.setToken(token);
    request.setSessionId(sessionId);
    
    grpc.unary(SessionManagerService.GetSession, {
      request,
      host,
      onEnd: (response) => {
        const { status, statusMessage, message } = response;
        
        if (status === grpc.Code.OK && message) {
          const getResponse = message as GetSessionResponse;
          resolve({
            sessionActive: getResponse.getSessionActive(),
            simulatorEndpoint: getResponse.getSimulatorEndpoint(),
            errorMessage: getResponse.getErrorMessage()
          });
        } else {
          reject(new Error(statusMessage || 'Unknown error'));
        }
      }
    });
  });
};

export const endSession = (token: string, sessionId: string): Promise<{
  success: boolean;
  errorMessage?: string;
}> => {
  return new Promise((resolve, reject) => {
    const request = new EndSessionRequest();
    request.setToken(token);
    request.setSessionId(sessionId);
    
    grpc.unary(SessionManagerService.EndSession, {
      request,
      host,
      onEnd: (response) => {
        const { status, statusMessage, message } = response;
        
        if (status === grpc.Code.OK && message) {
          const endResponse = message as EndSessionResponse;
          resolve({
            success: endResponse.getSuccess(),
            errorMessage: endResponse.getErrorMessage()
          });
        } else {
          reject(new Error(statusMessage || 'Unknown error'));
        }
      }
    });
  });
};

export const keepAlive = (token: string, sessionId: string): Promise<boolean> => {
  return new Promise((resolve, reject) => {
    const request = new KeepAliveRequest();
    request.setToken(token);
    request.setSessionId(sessionId);
    
    grpc.unary(SessionManagerService.KeepAlive, {
      request,
      host,
      onEnd: (response) => {
        const { status, statusMessage, message } = response;
        
        if (status === grpc.Code.OK && message) {
          const keepAliveResponse = message as KeepAliveResponse;
          resolve(keepAliveResponse.getSuccess());
        } else {
          reject(new Error(statusMessage || 'Unknown error'));
        }
      }
    });
  });
};