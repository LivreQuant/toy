import { BaseStateService } from './base-state-service';
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
export interface PortfolioState {
    lastUpdated: number;
    cash: number;
    positions: Record<string, Position>;
    orders: Record<string, Order>;
}
export declare const initialPortfolioState: PortfolioState;
export declare class PortfolioStateService extends BaseStateService<PortfolioState> {
    constructor();
    updateState(changes: Partial<PortfolioState>): void;
    updateOrder(orderData: Order): void;
    updatePosition(symbol: string, positionData: Position): void;
    reset(): void;
}
export declare const portfolioState: PortfolioStateService;
