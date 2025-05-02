// src/api/auth.ts
import { HttpClient } from './http-client';

export interface LoginRequest {
  username: string;
  password: string;
  rememberMe?: boolean;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  userId: number;
}

export interface SignupRequest {
  username: string;
  email: string;
  password: string;
}

export interface SignupResponse {
  success: boolean;
  userId?: number;
  error?: string;
  message?: string;
}

export interface VerifyEmailRequest {
  userId: string | number;
  code: string;
}

export interface ResendVerificationRequest {
  userId: string | number;
}

export interface ForgotUsernameRequest {
  email: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  newPassword: string;
}

export interface BaseResponse {
  success: boolean;
  error?: string;
  message?: string;
}

export class AuthApi {
  private client: HttpClient;

  constructor(client: HttpClient) {
    this.client = client;
  }

  async login(username: string, password: string, rememberMe: boolean = false): Promise<LoginResponse> {
    return this.client.post<LoginResponse>(
      '/auth/login',
      { username, password, rememberMe },
      { skipAuth: true }
    );
  }

  async logout(): Promise<void> {
    return this.client.post<void>('/auth/logout');
  }

  async refreshToken(refreshToken: string): Promise<LoginResponse> {
    return this.client.post<LoginResponse>(
      '/auth/refresh',
      { refreshToken },
      { skipAuth: true }
    );
  }

  async signup(data: SignupRequest): Promise<SignupResponse> {
    return this.client.post<SignupResponse>(
      '/auth/signup',
      data,
      { skipAuth: true }
    );
  }

  async verifyEmail(data: VerifyEmailRequest): Promise<BaseResponse> {
    return this.client.post<BaseResponse>(
      '/auth/verify-email',
      data,
      { skipAuth: true }
    );
  }

  async resendVerification(data: ResendVerificationRequest): Promise<BaseResponse> {
    return this.client.post<BaseResponse>(
      '/auth/resend-verification',
      data,
      { skipAuth: true }
    );
  }

  async forgotUsername(data: ForgotUsernameRequest): Promise<BaseResponse> {
    return this.client.post<BaseResponse>(
      '/auth/forgot-username',
      data,
      { skipAuth: true }
    );
  }

  async forgotPassword(data: ForgotPasswordRequest): Promise<BaseResponse> {
    return this.client.post<BaseResponse>(
      '/auth/forgot-password',
      data,
      { skipAuth: true }
    );
  }

  async resetPassword(data: ResetPasswordRequest): Promise<BaseResponse> {
    return this.client.post<BaseResponse>(
      '/auth/reset-password',
      data,
      { skipAuth: true }
    );
  }
}
