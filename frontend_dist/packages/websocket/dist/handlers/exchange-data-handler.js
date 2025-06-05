// src/handlers/exchange-data-handler.ts
import { getLogger } from '@trading-app/logging';
export class ExchangeDataHandler {
    constructor(client, stateManager) {
        this.client = client;
        this.stateManager = stateManager;
        this.logger = getLogger('ExchangeDataHandler');
        this.setupListeners();
        this.logger.info('ExchangeDataHandler initialized');
    }
    setupListeners() {
        this.client.on('message', (message) => {
            if (message.type === 'exchange_data') {
                this.handleExchangeData(message);
            }
        });
    }
    handleExchangeData(message) {
        this.logger.debug('Received exchange data', {
            symbolCount: Object.keys(message.symbols || {}).length,
            hasOrderData: !!message.userOrders,
            hasPositionData: !!message.userPositions,
        });
        // Process market data
        if (message.symbols) {
            const marketData = Object.entries(message.symbols).reduce((acc, [symbol, data]) => {
                acc[symbol] = {
                    price: data.price,
                    open: data.price - (data.change || 0),
                    high: data.price,
                    low: data.price,
                    close: data.price,
                    volume: data.volume || 0
                };
                return acc;
            }, {});
            this.stateManager.updateExchangeState({ symbols: marketData });
        }
        // Process portfolio data
        if (message.userOrders || message.userPositions) {
            const portfolioUpdate = {};
            if (message.userOrders) {
                const orders = Object.entries(message.userOrders).reduce((acc, [orderId, data]) => {
                    acc[orderId] = {
                        orderId,
                        symbol: data.orderId.split('-')[0] || 'UNKNOWN',
                        status: data.status,
                        filledQty: data.filledQty,
                        remainingQty: 0,
                        timestamp: message.timestamp
                    };
                    return acc;
                }, {});
                portfolioUpdate.orders = orders;
            }
            if (message.userPositions) {
                const positions = Object.entries(message.userPositions).reduce((acc, [symbol, data]) => {
                    acc[symbol] = {
                        symbol,
                        quantity: data.quantity,
                        avgPrice: data.value / data.quantity,
                        marketValue: data.value
                    };
                    return acc;
                }, {});
                portfolioUpdate.positions = positions;
            }
            this.stateManager.updatePortfolioState(portfolioUpdate);
        }
    }
}
