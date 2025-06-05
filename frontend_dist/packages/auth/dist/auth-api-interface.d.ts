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
/**
 * Interface for authentication API
 * This allows the TokenManager to work with different API implementations
 */
export interface AuthApiInterface {
    /**
     * Refreshes an access token using a refresh token
     * @param refreshToken - The refresh token to use
     * @returns Promise with the refresh response
     */
    refreshToken(refreshToken: string): Promise<LoginResponse>;
}
