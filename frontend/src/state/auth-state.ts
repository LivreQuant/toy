// src/state/auth-state.ts
import { BehaviorSubject, Observable } from 'rxjs';
import { map, distinctUntilChanged } from 'rxjs/operators';
import { getLogger } from '../boot/logging';

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
export class AuthStateService {
  private state$ = new BehaviorSubject<AuthState>(initialAuthState);
  private logger = getLogger('AuthStateService');

  // Select a slice of the auth state
  select<T>(selector: (state: AuthState) => T): Observable<T> {
    return this.state$.pipe(
      map(selector),
      distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))
    );
  }

  // Get the entire auth state as an observable
  getState$(): Observable<AuthState> {
    return this.state$.asObservable();
  }

  // Get the current state snapshot
  getState(): AuthState {
    return this.state$.getValue();
  }

  // Update the auth state
  updateState(changes: Partial<AuthState>): void {
    const currentState = this.getState();
    const newState: AuthState = {
      ...currentState,
      ...changes
    };
    
    this.logger.debug('Updating auth state', changes);
    this.state$.next(newState);
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
}

// Export singleton instance
export const authState = new AuthStateService();