// src/state/portfolio-state.ts
import { BehaviorSubject, Observable } from 'rxjs';
import { map, distinctUntilChanged } from 'rxjs/operators';

import { getLogger } from '../boot/logging';

// Define position and order structures
export interface Position {
  symbol: string;
  quantity: number;
  avgPrice: number;
  marketValue?: number;
  unrealizedPnl?: number;
}

export interface Order {
  orderId: string;
  symbol: string;
  status: string;
  filledQty: number;
  remainingQty: number;
  price?: number;
  timestamp: number;
}

// Define the portfolio state interface
export interface PortfolioState {
  lastUpdated: number;
  cash: number;
  positions: Record<string, Position>;
  orders: Record<string, Order>;
}

// Initial portfolio state
export const initialPortfolioState: PortfolioState = {
  lastUpdated: 0,
  cash: 0,
  positions: {},
  orders: {},
};

// Portfolio state service
export class PortfolioStateService {
  private state$ = new BehaviorSubject<PortfolioState>(initialPortfolioState);
  private logger = getLogger('PortfolioStateService');

  // Select a slice of the portfolio state
  select<T>(selector: (state: PortfolioState) => T): Observable<T> {
    return this.state$.pipe(
      map(selector),
      distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))
    );
  }

  // Get the entire portfolio state as an observable
  getState$(): Observable<PortfolioState> {
    return this.state$.asObservable();
  }

  // Get the current state snapshot
  getState(): PortfolioState {
    return this.state$.getValue();
  }

  // Update portfolio state
  updateState(changes: Partial<PortfolioState>): void {
    const currentState = this.getState();
    const newState: PortfolioState = {
      ...currentState,
      ...changes,
      lastUpdated: Date.now()
    };
    
    this.logger.debug('Updating portfolio state', changes);
    this.state$.next(newState);
  }

  // Update a specific order
  updateOrder(orderData: Order): void {
    const currentState = this.getState();
    const updatedOrders = {
      ...currentState.orders,
      [orderData.orderId]: orderData
    };
    
    this.logger.debug(`Updating portfolio order: ${orderData.orderId}`, orderData);
    
    this.state$.next({
      ...currentState,
      orders: updatedOrders,
      lastUpdated: Date.now()
    });
  }

  // Update a specific position
  updatePosition(symbol: string, positionData: Position): void {
    const currentState = this.getState();
    const updatedPositions = {
      ...currentState.positions,
      [symbol]: positionData
    };
    
    this.state$.next({
      ...currentState,
      positions: updatedPositions,
      lastUpdated: Date.now()
    });
  }
}

// Export singleton instance
export const portfolioState = new PortfolioStateService();