// src/services/grpc/auth.ts
import { grpc } from '@improbable-eng/grpc-web';
import { AuthService } from '../../generated/auth_pb_service';
import { LoginRequest, LoginResponse, LogoutRequest, LogoutResponse, ValidateTokenRequest, ValidateTokenResponse } from '../../generated/auth_pb';

const host = 'http://localhost:8080';

export const login = (username: string, password: string): Promise<{
  success: boolean;
  token: string;
  errorMessage?: string;
}> => {
  return new Promise((resolve, reject) => {
    const request = new LoginRequest();
    request.setUsername(username);
    request.setPassword(password);
    
    grpc.unary(AuthService.Login, {
      request,
      host,
      onEnd: (response) => {
        const { status, statusMessage, message } = response;
        
        if (status === grpc.Code.OK && message) {
          const loginResponse = message as LoginResponse;
          resolve({
            success: loginResponse.getSuccess(),
            token: loginResponse.getToken(),
            errorMessage: loginResponse.getErrorMessage()
          });
        } else {
          reject(new Error(statusMessage || 'Unknown error'));
        }
      }
    });
  });
};

export const logout = (token: string): Promise<boolean> => {
  return new Promise((resolve, reject) => {
    const request = new LogoutRequest();
    request.setToken(token);
    
    grpc.unary(AuthService.Logout, {
      request,
      host,
      onEnd: (response) => {
        const { status, statusMessage, message } = response;
        
        if (status === grpc.Code.OK && message) {
          const logoutResponse = message as LogoutResponse;
          resolve(logoutResponse.getSuccess());
        } else {
          reject(new Error(statusMessage || 'Unknown error'));
        }
      }
    });
  });
};

export const validateToken = (token: string): Promise<{
  valid: boolean;
  userId?: string;
}> => {
  return new Promise((resolve, reject) => {
    const request = new ValidateTokenRequest();
    request.setToken(token);
    
    grpc.unary(AuthService.ValidateToken, {
      request,
      host,
      onEnd: (response) => {
        const { status, statusMessage, message } = response;
        
        if (status === grpc.Code.OK && message) {
          const validateResponse = message as ValidateTokenResponse;
          resolve({
            valid: validateResponse.getValid(),
            userId: validateResponse.getUserId()
          });
        } else {
          reject(new Error(statusMessage || 'Unknown error'));
        }
      }
    });
  });
};