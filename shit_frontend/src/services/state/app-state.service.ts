// src/services/state/app-state.service.ts
import { BehaviorSubject, Observable } from 'rxjs';
import { map, distinctUntilChanged } from 'rxjs/operators';
import { ConnectionStatus, ConnectionQuality } from '../connection/unified-connection-state';

// Define the structure of our application state
export interface AppState {
  connection: {
    status: ConnectionStatus;
    quality: ConnectionQuality;
    isRecovering: boolean;
    recoveryAttempt: number;
    lastHeartbeatTime?: number;
    heartbeatLatency?: number | null;
    simulatorStatus: string;
  };
  auth: {
    isAuthenticated: boolean;
    isLoading: boolean;
    userId: string | number | null;
  };
  exchange: {
    data: Record<string, any>;
    lastUpdated: number;
  };
  portfolio: {
    positions: Record<string, any>;
    orders: Record<string, any>;
    cash: number;
    lastUpdated: number;
  };
}

// Initial state values
const initialState: AppState = {
  connection: {
    status: ConnectionStatus.DISCONNECTED,
    quality: ConnectionQuality.UNKNOWN,
    isRecovering: false,
    recoveryAttempt: 0,
    simulatorStatus: 'UNKNOWN',
  },
  auth: {
    isAuthenticated: false,
    isLoading: true,
    userId: null,
  },
  exchange: {
    data: {},
    lastUpdated: 0,
  },
  portfolio: {
    positions: {},
    orders: {},
    cash: 0,
    lastUpdated: 0,
  },
};

export class AppStateService {
  private state$ = new BehaviorSubject<AppState>(initialState);

  // Selector helper to get a slice of state
  select<T>(selector: (state: AppState) => T): Observable<T> {
    return this.state$.pipe(
      map(selector),
      distinctUntilChanged()
    );
  }

  // Get current state snapshot
  getState(): AppState {
    return this.state$.getValue();
  }

  // Update state with partial changes
  update(stateChanges: Partial<AppState>): void {
    this.state$.next({
      ...this.getState(),
      ...stateChanges
    });
  }

  // Updates for specific slices
  updateConnection(connectionState: Partial<AppState['connection']>): void {
    const currentState = this.getState();
    this.update({
      connection: {
        ...currentState.connection,
        ...connectionState
      }
    });
  }

  updateAuth(authState: Partial<AppState['auth']>): void {
    const currentState = this.getState();
    this.update({
      auth: {
        ...currentState.auth,
        ...authState
      }
    });
  }

  updateExchangeData(data: Record<string, any>): void {
    const currentState = this.getState();
    this.update({
      exchange: {
        data: { ...currentState.exchange.data, ...data },
        lastUpdated: Date.now()
      }
    });
  }

  updatePortfolio(portfolioChanges: Partial<AppState['portfolio']>): void {
    const currentState = this.getState();
    this.update({
      portfolio: {
        ...currentState.portfolio,
        ...portfolioChanges,
        lastUpdated: Date.now()
      }
    });
  }

  // Singleton pattern
  private static instance: AppStateService | null = null;

  static getInstance(): AppStateService {
    if (!AppStateService.instance) {
      AppStateService.instance = new AppStateService();
    }
    return AppStateService.instance;
  }
}

// Export singleton instance
export const appState = AppStateService.getInstance();