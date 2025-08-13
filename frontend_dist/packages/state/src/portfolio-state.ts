// frontend_dist/packages/state/src/portfolio-state.ts
import { BaseStateService } from './base-state-service';

// Define position structure for new format
export interface Position {
  symbol: string;
  quantity: number;
  avgPrice: number;
  marketValue?: number;
  unrealizedPnl?: number;
  average_price?: number; // New format field
  market_value?: number;  // New format field
  unrealized_pnl?: number; // New format field
  metadata?: Record<string, any>;
}

// Define order structure for new format
export interface Order {
  orderId: string;
  symbol: string;
  side?: 'BUY' | 'SELL';
  quantity?: number;
  price?: number;
  status: string;
  filledQty?: number;
  remainingQty?: number;
  timestamp: number;
  exchange_type?: string;
  metadata?: Record<string, any>;
}

// Define portfolio data structure from exchange_data
export interface PortfolioData {
  positions: Position[];
  cash_balance: number;
  total_value: number;
  exchange_type: string;
  metadata: Record<string, any>;
}

// Define the portfolio state interface
export interface PortfolioState {
  lastUpdated: number;
  sequenceNumber: number;
  // Legacy fields
  cash: number;
  positions: Record<string, Position>;
  orders: Record<string, Order>;
  // New fields from exchange_data
  portfolioData: PortfolioData | null;
  cashBalance: number;
  totalValue: number;
  dataSource: 'legacy' | 'exchange_data';
}

// Initial portfolio state
export const initialPortfolioState: PortfolioState = {
  lastUpdated: 0,
  sequenceNumber: 0,
  cash: 0,
  positions: {},
  orders: {},
  portfolioData: null,
  cashBalance: 0,
  totalValue: 0,
  dataSource: 'legacy'
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

  // NEW: Update order data from exchange_data messages
  updateOrderData(orderDataArray: Order[]): void {
    this.logger.debug(`Updating order data (count: ${orderDataArray.length})`);
    
    const ordersMap: Record<string, Order> = {};
    orderDataArray.forEach(order => {
      ordersMap[order.orderId] = order;
    });

    this.updateState({
      orders: ordersMap,
      dataSource: 'exchange_data'
    });
  }

  // NEW: Update portfolio data from exchange_data messages
  updatePortfolioData(portfolioData: PortfolioData): void {
    this.logger.debug('Updating portfolio data', portfolioData);
    
    // Convert positions array to map for consistency with legacy format
    const positionsMap: Record<string, Position> = {};
    portfolioData.positions.forEach(position => {
      positionsMap[position.symbol] = {
        ...position,
        // Map new format fields to legacy fields
        avgPrice: position.average_price || position.avgPrice || 0,
        marketValue: position.market_value || position.marketValue || 0,
        unrealizedPnl: position.unrealized_pnl || position.unrealizedPnl || 0
      };
    });

    this.updateState({
      portfolioData,
      positions: positionsMap,
      cashBalance: portfolioData.cash_balance,
      totalValue: portfolioData.total_value,
      cash: portfolioData.cash_balance, // Update legacy field too
      dataSource: 'exchange_data'
    });
  }

  // NEW: Update sequence number for delta tracking
  updateSequenceNumber(sequenceNumber: number): void {
    this.updateState({ sequenceNumber });
  }

  // LEGACY: Update a specific order (keep for backward compatibility)
  updateOrder(orderData: Order): void {
    const currentState = this.getState();
    const updatedOrders = {
      ...currentState.orders,
      [orderData.orderId]: orderData
    };
    
    this.logger.debug(`Updating portfolio order: ${orderData.orderId}`, orderData);
    
    this.updateState({
      orders: updatedOrders,
      dataSource: 'legacy'
    });
  }

  // LEGACY: Update a specific position (keep for backward compatibility)
  updatePosition(symbol: string, positionData: Position): void {
    const currentState = this.getState();
    const updatedPositions = {
      ...currentState.positions,
      [symbol]: positionData
    };
    
    this.updateState({
      positions: updatedPositions,
      dataSource: 'legacy'
    });
  }

  // NEW: Get all orders as array
  getAllOrders(): Order[] {
    const currentState = this.getState();
    return Object.values(currentState.orders);
  }

  // NEW: Get all positions as array
  getAllPositions(): Position[] {
    const currentState = this.getState();
    return Object.values(currentState.positions);
  }

  // NEW: Get portfolio summary
  getPortfolioSummary(): {
    totalValue: number;
    cashBalance: number;
    positionsValue: number;
    unrealizedPnl: number;
  } {
    const currentState = this.getState();
    const positions = Object.values(currentState.positions);
    
    const positionsValue = positions.reduce((sum, pos) => 
      sum + (pos.marketValue || pos.market_value || 0), 0);
    
    const unrealizedPnl = positions.reduce((sum, pos) => 
      sum + (pos.unrealizedPnl || pos.unrealized_pnl || 0), 0);

    return {
      totalValue: currentState.totalValue || currentState.cash + positionsValue,
      cashBalance: currentState.cashBalance || currentState.cash,
      positionsValue,
      unrealizedPnl
    };
  }

  reset(): void {
    this.setState(initialPortfolioState);
  }
}

// Export singleton instance
export const portfolioState = new PortfolioStateService();