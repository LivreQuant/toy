// src/services/state/app-state.service.ts
import { BehaviorSubject, Observable } from 'rxjs';
import { map, distinctUntilChanged } from 'rxjs/operators'; // Removed filter as it wasn't used directly here
import { getLogger } from '../../boot/logging'; // Import logger

// Enums can be defined here or imported if needed elsewhere
export enum ConnectionStatus {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  RECOVERING = 'recovering'
}

export enum ConnectionQuality {
  GOOD = 'good',
  DEGRADED = 'degraded',
  POOR = 'poor',
  UNKNOWN = 'unknown'
}
// --- End Enums ---


// Define the structure of our application state
export interface AppState {
  connection: {
    overallStatus: ConnectionStatus; // Derived or directly set status
    webSocketStatus: ConnectionStatus; // Specific status of the WS connection
    quality: ConnectionQuality;
    isRecovering: boolean;
    recoveryAttempt: number;
    lastHeartbeatTime?: number; // Milliseconds timestamp
    heartbeatLatency?: number | null; // Milliseconds
    simulatorStatus: string; // e.g., 'RUNNING', 'STOPPED', 'STARTING', 'STOPPING', 'ERROR', 'UNKNOWN'
    lastConnectionError: string | null;
  };
  auth: {
    isAuthenticated: boolean;
    isAuthLoading: boolean;
    userId: string | number | null;
    lastAuthError: string | null;
  };
  exchange: {
    lastUpdated: number; // Timestamp
    symbols: Record<string, { // Example structure for symbol data
        price: number;
        open: number;
        high: number;
        low: number;
        close: number;
        volume: number;
      }>;
  };
  portfolio: {
    lastUpdated: number; // Timestamp
    cash: number;
    positions: Record<string, { // Example structure for positions
        symbol: string;
        quantity: number;
        avgPrice: number;
        marketValue?: number; // FIX: Make optional to match incoming data possibility
        unrealizedPnl?: number; // FIX: Make optional to match incoming data possibility
      }>;
    orders: Record<string, { // Example structure for orders
        orderId: string;
        symbol: string;
        status: string; // e.g., 'NEW', 'FILLED', 'CANCELED'
        filledQty: number;
        remainingQty: number;
        price?: number;
        timestamp: number;
      }>;
  };
  // Add other application state slices as needed (e.g., UI settings)
  // ui: {
  //   theme: 'light' | 'dark';
  //   isSidebarOpen: boolean;
  // }
}

// FIX: Export initialState
// Initial state values
export const initialState: AppState = {
  connection: {
    overallStatus: ConnectionStatus.DISCONNECTED,
    webSocketStatus: ConnectionStatus.DISCONNECTED,
    quality: ConnectionQuality.UNKNOWN,
    isRecovering: false,
    recoveryAttempt: 0,
    simulatorStatus: 'UNKNOWN',
    lastConnectionError: null,
  },
  auth: {
    isAuthenticated: false,
    isAuthLoading: true, // Start loading auth state
    userId: null,
    lastAuthError: null,
  },
  exchange: {
    lastUpdated: 0,
    symbols: {},
  },
  portfolio: {
    lastUpdated: 0,
    cash: 0,
    positions: {},
    orders: {},
  },
  // ui: {
  //   theme: 'light',
  //   isSidebarOpen: true,
  // }
};

export class AppStateService {
  private state$ = new BehaviorSubject<AppState>(initialState);
  private logger = getLogger('AppStateService');

  // --- Selectors ---

  // Selector helper to get a slice of state and ensure emissions only on change
  select<T>(selector: (state: AppState) => T): Observable<T> {
    console.log("*** AppState: select() called ***");
    return this.state$.pipe(
      map(state => {
        const result = selector(state);
        console.log("*** AppState: select() emitting value ***", { result });
        return result;
      }),
      distinctUntilChanged((prev, curr) => {
        const isEqual = JSON.stringify(prev) === JSON.stringify(curr);
        console.log("*** AppState: distinctUntilChanged() ***", { 
          prev, curr, isEqual, willEmit: !isEqual 
        });
        return isEqual;
      })
    );
  }

  // Convenience selector for the entire state (emits on any change)
  getState$(): Observable<AppState> {
    return this.state$.asObservable();
  }

  // Convenience selector for connection state
  getConnectionState$(): Observable<AppState['connection']> {
    return this.select(state => state.connection);
  }

   // Convenience selector for auth state
  getAuthState$(): Observable<AppState['auth']> {
    return this.select(state => state.auth);
  }

  // --- Getters ---

  // Get current state snapshot
  getState(): AppState {
    return this.state$.getValue();
  }

  // --- Updaters ---

  // Generic update (use with caution, prefer specific updaters)
  // private update(stateChanges: Partial<AppState>): void {
  //   this.state$.next({ ...this.getState(), ...stateChanges });
  // }

  // Update connection state slice
  updateConnectionState(connectionChanges: Partial<AppState['connection']>): void {
    const currentState = this.getState();
    // Recalculate overall status if specific statuses change
    let newOverallStatus = connectionChanges.overallStatus ?? currentState.connection.overallStatus;
    if (connectionChanges.webSocketStatus || connectionChanges.isRecovering !== undefined) {
        const wsStatus = connectionChanges.webSocketStatus ?? currentState.connection.webSocketStatus;
        const isRecovering = connectionChanges.isRecovering ?? currentState.connection.isRecovering;

        if (isRecovering) {
            newOverallStatus = ConnectionStatus.RECOVERING;
        } else {
            // Define logic for overall status based on primary connection (WebSocket)
            // Example: Overall = WebSocket status if not recovering
            newOverallStatus = wsStatus;
        }
    }


    const newState: AppState = {
      ...currentState,
      connection: {
        ...currentState.connection,
        ...connectionChanges,
        overallStatus: newOverallStatus, // Set the calculated overall status
      }
    };
    this.logger.debug('Updating connection state', connectionChanges);
    this.state$.next(newState);
  }

  // Update auth state slice
  updateAuthState(authChanges: Partial<AppState['auth']>): void {
    const currentState = this.getState();
    const newState: AppState = {
      ...currentState,
      auth: {
        ...currentState.auth,
        ...authChanges
      }
    };
     this.logger.debug('Updating auth state', authChanges);
    this.state$.next(newState);
  }

  // Update exchange data (example: replace all symbols)
  updateExchangeSymbols(symbolsData: AppState['exchange']['symbols']): void {
    const currentState = this.getState();
     this.logger.debug(`Updating exchange symbols (count: ${Object.keys(symbolsData).length})`);
    this.state$.next({
      ...currentState,
      exchange: {
        symbols: symbolsData,
        lastUpdated: Date.now()
      }
    });
  }

   // Update portfolio data (example: merging changes)
  updatePortfolioState(portfolioChanges: Partial<AppState['portfolio']>): void {
    const currentState = this.getState();
     this.logger.debug('Updating portfolio state', portfolioChanges);
    this.state$.next({
      ...currentState,
      portfolio: {
        ...currentState.portfolio,
        ...portfolioChanges,
        lastUpdated: Date.now()
      }
    });
  }

   // Update a specific order in the portfolio
  updatePortfolioOrder(orderData: AppState['portfolio']['orders'][string]): void {
    const currentState = this.getState();
    const updatedOrders = {
       ...currentState.portfolio.orders,
       [orderData.orderId]: orderData
    };
    this.logger.debug(`Updating portfolio order: ${orderData.orderId}`, orderData);
    this.state$.next({
       ...currentState,
       portfolio: {
         ...currentState.portfolio,
         orders: updatedOrders,
         lastUpdated: Date.now() // Also update portfolio timestamp
       }
    });
   }

  // Calculate connection quality based on latency
  calculateConnectionQuality(latency: number | null): ConnectionQuality {
    if (latency === null || latency < 0) return ConnectionQuality.UNKNOWN;
    if (latency <= 250) return ConnectionQuality.GOOD;
    if (latency <= 750) return ConnectionQuality.DEGRADED;
    return ConnectionQuality.POOR;
  }

  // --- Singleton Pattern ---
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