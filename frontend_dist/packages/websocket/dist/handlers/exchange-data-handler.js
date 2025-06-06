// src/handlers/exchange-data-handler.ts
import { getLogger } from '@trading-app/logging';
var ExchangeDataHandler = /** @class */ (function () {
    function ExchangeDataHandler(client, stateManager) {
        this.client = client;
        this.stateManager = stateManager;
        this.logger = getLogger('ExchangeDataHandler');
        this.setupListeners();
        this.logger.info('ExchangeDataHandler initialized');
    }
    ExchangeDataHandler.prototype.setupListeners = function () {
        var _this = this;
        this.client.on('message', function (message) {
            if (message.type === 'exchange_data') {
                _this.handleExchangeData(message);
            }
        });
    };
    ExchangeDataHandler.prototype.handleExchangeData = function (message) {
        this.logger.debug('Received exchange data', {
            symbolCount: Object.keys(message.symbols || {}).length,
            hasOrderData: !!message.userOrders,
            hasPositionData: !!message.userPositions,
        });
        // Process market data
        if (message.symbols) {
            var marketData = Object.entries(message.symbols).reduce(function (acc, _a) {
                var symbol = _a[0], data = _a[1];
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
            var portfolioUpdate = {};
            if (message.userOrders) {
                var orders = Object.entries(message.userOrders).reduce(function (acc, _a) {
                    var orderId = _a[0], data = _a[1];
                    acc[orderId] = {
                        orderId: orderId,
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
                var positions = Object.entries(message.userPositions).reduce(function (acc, _a) {
                    var symbol = _a[0], data = _a[1];
                    acc[symbol] = {
                        symbol: symbol,
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
    };
    return ExchangeDataHandler;
}());
export { ExchangeDataHandler };
