// frontend_dist/packages/api/src/types/auth-types.ts
export interface LoginRequest {
    username: string;
    password: string;
  }
  
  export interface LoginResponse {
    success: boolean;
    accessToken?: string;
    refreshToken?: string;
    expiresIn?: number;
    userId?: string | number;
    userRole?: string;
    requiresVerification?: boolean;
    email?: string;
    error?: string;
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