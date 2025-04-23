// src/services/websocket/message-handlers/exchange-data.ts
import { getLogger } from '../../../boot/logging';

import { SocketClient } from '../../connection/socket-client';

import { ServerExchangeDataMessage } from '../message-types';

import { exchangeState } from '../../../state/exchange-state';
import { portfolioState } from '../../../state/portfolio-state';

export class ExchangeDataHandler {
  private logger = getLogger('ExchangeDataHandler');
  private client: SocketClient;
  
  constructor(client: SocketClient) {
    this.client = client;
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
          open: data.price - (data.change || 0), // Estimate
          high: data.price, // Default value
          low: data.price, // Default value
          close: data.price, // Default value
          volume: data.volume || 0
        };
        return acc;
      }, {} as Record<string, { price: number; open: number; high: number; low: number; close: number; volume: number; }>);
      
      exchangeState.updateSymbols(marketData);
    }
    
    // Process portfolio data
    if (message.userOrders || message.userPositions) {
      // Convert orders format if needed
      if (message.userOrders) {
        const orders = Object.entries(message.userOrders).reduce((acc, [orderId, data]) => {
          acc[orderId] = {
            orderId,
            symbol: data.orderId.split('-')[0] || 'UNKNOWN', // Extract symbol from orderId if available
            status: data.status,
            filledQty: data.filledQty,
            remainingQty: 0, // Not provided in message, calculate if needed
            timestamp: message.timestamp
          };
          return acc;
        }, {} as Record<string, { orderId: string; symbol: string; status: string; filledQty: number; remainingQty: number; timestamp: number; }>);
        
        portfolioState.updateState({ orders });
      }
      
      // Convert positions format if needed
      if (message.userPositions) {
        const positions = Object.entries(message.userPositions).reduce((acc, [symbol, data]) => {
          acc[symbol] = {
            symbol,
            quantity: data.quantity,
            avgPrice: data.value / data.quantity, // Calculate average price
            marketValue: data.value
          };
          return acc;
        }, {} as Record<string, { symbol: string; quantity: number; avgPrice: number; marketValue: number; }>);
        
        portfolioState.updateState({ positions });
      }
    }
  }
}