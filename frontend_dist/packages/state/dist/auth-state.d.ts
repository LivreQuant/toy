import { BaseStateService } from './base-state-service';
export interface AuthState {
    isAuthenticated: boolean;
    isAuthLoading: boolean;
    userId: string | number | null;
    lastAuthError: string | null;
}
export declare const initialAuthState: AuthState;
export declare class AuthStateService extends BaseStateService<AuthState> {
    constructor();
    setAuthenticated(userId: string | number): void;
    setUnauthenticated(error?: string): void;
    setLoading(isLoading: boolean): void;
    reset(): void;
}
export declare const authState: AuthStateService;
