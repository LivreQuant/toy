// src/portfolio-state.ts
import { BaseStateService } from './base-state-service';

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
export class PortfolioStateService extends BaseStateService<PortfolioState> {
  constructor() {
    super(initialPortfolioState);
  }

  // Override updateState to always update lastUpdated
  updateState(changes: Partial<PortfolioState>): void {
    super.updateState({
      ...changes,
      lastUpdated: Date.now()
    });
  }

  // Update a specific order
  updateOrder(orderData: Order): void {
    const currentState = this.getState();
    const updatedOrders = {
      ...currentState.orders,
      [orderData.orderId]: orderData
    };
    
    this.logger.debug(`Updating portfolio order: ${orderData.orderId}`, orderData);
    
    this.updateState({
      orders: updatedOrders
    });
  }

  // Update a specific position
  updatePosition(symbol: string, positionData: Position): void {
    const currentState = this.getState();
    const updatedPositions = {
      ...currentState.positions,
      [symbol]: positionData
    };
    
    this.updateState({
      positions: updatedPositions
    });
  }

  reset(): void {
    this.setState(initialPortfolioState);
  }
}

// Export singleton instance
export const portfolioState = new PortfolioStateService();