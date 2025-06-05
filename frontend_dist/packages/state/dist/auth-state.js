// src/auth-state.ts
import { BaseStateService } from './base-state-service';
// Initial auth state
export const initialAuthState = {
    isAuthenticated: false,
    isAuthLoading: true,
    userId: null,
    lastAuthError: null,
};
// Auth state service
export class AuthStateService extends BaseStateService {
    constructor() {
        super(initialAuthState);
    }
    // Set authenticated state
    setAuthenticated(userId) {
        this.updateState({
            isAuthenticated: true,
            isAuthLoading: false,
            userId,
            lastAuthError: null
        });
    }
    // Set unauthenticated state
    setUnauthenticated(error) {
        this.updateState({
            isAuthenticated: false,
            isAuthLoading: false,
            userId: null,
            lastAuthError: error || null
        });
    }
    // Set loading state
    setLoading(isLoading) {
        this.updateState({ isAuthLoading: isLoading });
    }
    // Reset to initial state
    reset() {
        this.setState(initialAuthState);
    }
}
// Export singleton instance
export const authState = new AuthStateService();
