// src/handlers/exchange-data-handler.ts
import { getLogger } from '@trading-app/logging';

import { SocketClient } from '../client/socket-client';
import { ServerExchangeDataMessage } from '../types/message-types';
import { StateManager } from '../types/connection-types';

export class ExchangeDataHandler {
  private logger = getLogger('ExchangeDataHandler');
  
  constructor(private client: SocketClient, private stateManager: StateManager) {
    this.setupListeners();
    this.logger.info('ExchangeDataHandler initialized');
  }

  private setupListeners(): void {
    this.client.on('message', (message) => {
      if (message.type === 'exchange_data') {
        this.handleExchangeData(message as ServerExchangeDataMessage);
      }
    });
  }

  private handleExchangeData(message: ServerExchangeDataMessage): void {
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
      }, {} as Record<string, { price: number; open: number; high: number; low: number; close: number; volume: number; }>);
      
      this.stateManager.updateExchangeState({ symbols: marketData });
    }
    
    // Process portfolio data
    if (message.userOrders || message.userPositions) {
      const portfolioUpdate: any = {};
      
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
        }, {} as Record<string, any>);
        
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
        }, {} as Record<string, any>);
        
        portfolioUpdate.positions = positions;
      }
      
      this.stateManager.updatePortfolioState(portfolioUpdate);
    }
  }
}