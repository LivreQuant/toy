import { HttpClient } from './http-client';
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
export declare class AuthApi {
    private client;
    constructor(client: HttpClient);
    login(username: string, password: string): Promise<LoginResponse>;
    logout(): Promise<void>;
    refreshToken(refreshToken: string): Promise<LoginResponse>;
    signup(data: SignupRequest): Promise<SignupResponse>;
    verifyEmail(data: VerifyEmailRequest): Promise<BaseResponse>;
    resendVerification(data: ResendVerificationRequest): Promise<BaseResponse>;
    forgotUsername(data: ForgotUsernameRequest): Promise<BaseResponse>;
    forgotPassword(data: ForgotPasswordRequest): Promise<BaseResponse>;
    resetPassword(data: ResetPasswordRequest): Promise<BaseResponse>;
}
