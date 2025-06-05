// src/portfolio-state.ts
import { BaseStateService } from './base-state-service';
// Initial portfolio state
export const initialPortfolioState = {
    lastUpdated: 0,
    cash: 0,
    positions: {},
    orders: {},
};
// Portfolio state service
export class PortfolioStateService extends BaseStateService {
    constructor() {
        super(initialPortfolioState);
    }
    // Override updateState to always update lastUpdated
    updateState(changes) {
        super.updateState(Object.assign(Object.assign({}, changes), { lastUpdated: Date.now() }));
    }
    // Update a specific order
    updateOrder(orderData) {
        const currentState = this.getState();
        const updatedOrders = Object.assign(Object.assign({}, currentState.orders), { [orderData.orderId]: orderData });
        this.logger.debug(`Updating portfolio order: ${orderData.orderId}`, orderData);
        this.updateState({
            orders: updatedOrders
        });
    }
    // Update a specific position
    updatePosition(symbol, positionData) {
        const currentState = this.getState();
        const updatedPositions = Object.assign(Object.assign({}, currentState.positions), { [symbol]: positionData });
        this.updateState({
            positions: updatedPositions
        });
    }
    reset() {
        this.setState(initialPortfolioState);
    }
}
// Export singleton instance
export const portfolioState = new PortfolioStateService();
