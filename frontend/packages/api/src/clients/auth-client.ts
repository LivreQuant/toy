// frontend_dist/packages/api/src/clients/auth-client.ts
import { BaseApiClient } from '../core/base-client';
import {
  LoginRequest,
  LoginResponse,
  SignupRequest,
  SignupResponse,
  VerifyEmailRequest,
  ResendVerificationRequest,
  ForgotUsernameRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  BaseResponse
} from '../types/auth-types';

export class AuthClient extends BaseApiClient {
  async login(username: string, password: string): Promise<LoginResponse> {
    this.logger.info("Attempting login for user:", username);
    
    try {
      const response = await this.post<LoginResponse>(
        '/auth/login',
        { username, password },
        { skipAuth: true }
      );
      
      this.logger.info("Login response received:", JSON.stringify(response));
      return response;
    } catch (error) {
      this.logger.error("Login request failed:", error);
      throw error;
    }
  }

  async logout(): Promise<void> {
    return this.post<void>('/auth/logout');
  }

  async refreshToken(refreshToken: string): Promise<LoginResponse> {
    return this.post<LoginResponse>(
      '/auth/refresh',
      { refreshToken },
      { skipAuth: true }
    );
  }

  async signup(data: SignupRequest): Promise<SignupResponse> {
    return this.post<SignupResponse>(
      '/auth/signup',
      data,
      { skipAuth: true }
    );
  }

  async verifyEmail(data: VerifyEmailRequest): Promise<BaseResponse> {
    return this.post<BaseResponse>(
      '/auth/verify-email',
      data,
      { skipAuth: true }
    );
  }

  async resendVerification(data: ResendVerificationRequest): Promise<BaseResponse> {
    return this.post<BaseResponse>(
      '/auth/resend-verification',
      data,
      { skipAuth: true }
    );
  }

  async forgotUsername(data: ForgotUsernameRequest): Promise<BaseResponse> {
    return this.post<BaseResponse>(
      '/auth/forgot-username',
      data,
      { skipAuth: true }
    );
  }

  async forgotPassword(data: ForgotPasswordRequest): Promise<BaseResponse> {
    return this.post<BaseResponse>(
      '/auth/forgot-password',
      data,
      { skipAuth: true }
    );
  }

  async resetPassword(data: ResetPasswordRequest): Promise<BaseResponse> {
    return this.post<BaseResponse>(
      '/auth/reset-password',
      data,
      { skipAuth: true }
    );
  }
}