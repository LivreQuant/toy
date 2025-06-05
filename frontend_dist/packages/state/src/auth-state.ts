// src/auth-state.ts
import { BaseStateService } from './base-state-service';

// Define the auth state interface
export interface AuthState {
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  userId: string | number | null;
  lastAuthError: string | null;
}

// Initial auth state
export const initialAuthState: AuthState = {
  isAuthenticated: false,
  isAuthLoading: true,
  userId: null,
  lastAuthError: null,
};

// Auth state service
export class AuthStateService extends BaseStateService<AuthState> {
  constructor() {
    super(initialAuthState);
  }

  // Set authenticated state
  setAuthenticated(userId: string | number): void {
    this.updateState({
      isAuthenticated: true,
      isAuthLoading: false,
      userId,
      lastAuthError: null
    });
  }

  // Set unauthenticated state
  setUnauthenticated(error?: string): void {
    this.updateState({
      isAuthenticated: false,
      isAuthLoading: false,
      userId: null,
      lastAuthError: error || null
    });
  }

  // Set loading state
  setLoading(isLoading: boolean): void {
    this.updateState({ isAuthLoading: isLoading });
  }

  // Reset to initial state
  reset(): void {
    this.setState(initialAuthState);
  }
}

// Export singleton instance
export const authState = new AuthStateService();