// frontend_dist/packages/websocket/src/handlers/exchange-data-handler.ts
import { getLogger } from '@trading-app/logging';

import { SocketClient } from '../client/socket-client';
import { ServerExchangeDataMessage } from '../types/message-types';
import { StateManager } from '../types/connection-types';

export class ExchangeDataHandler {
  private logger = getLogger('ExchangeDataHandler');
  private sequenceNumber = 0;
  private equityDataMap = new Map<string, any>();
  private ordersMap = new Map<string, any>();
  
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
    this.logger.info('📊 Processing exchange data message', {
      deltaType: message.deltaType,
      sequence: message.sequence,
      equityCount: message.data.equityData.length,
      orderCount: message.data.orders.length,
      hasPortfolio: !!message.data.portfolio
    });
    
    // Validate sequence order for delta messages
    if (message.deltaType === 'DELTA' && message.sequence <= this.sequenceNumber) {
      this.logger.warn('⚠️ Ignoring out-of-sequence delta message', {
        receivedSequence: message.sequence,
        currentSequence: this.sequenceNumber
      });
      return;
    }
    
    if (message.deltaType === 'FULL') {
      this.handleFullUpdate(message.data);
    } else if (message.deltaType === 'DELTA') {
      this.handleDeltaUpdate(message.data);
    }
    
    this.sequenceNumber = message.sequence;
  }

  private handleFullUpdate(data: any): void {
    this.logger.info('🔄 Processing FULL update');
    
    // Clear and rebuild equity data
    this.equityDataMap.clear();
    data.equityData.forEach((equity: any) => {
      this.equityDataMap.set(equity.symbol, equity);
    });
    
    // Clear and rebuild orders
    this.ordersMap.clear();
    data.orders.forEach((order: any) => {
      this.ordersMap.set(order.orderId, order);
    });
    
    // Update state
    this.emitUpdatedData();
    
    // Update portfolio directly
    if (data.portfolio) {
      this.stateManager.updatePortfolioData(data.portfolio);
    }
  }

  private handleDeltaUpdate(data: any): void {
    this.logger.info('📊 Processing DELTA update', {
      equityUpdates: data.equityData.length,
      orderUpdates: data.orders.length
    });
    
    // Update equity data
    data.equityData.forEach((equity: any) => {
      this.equityDataMap.set(equity.symbol, equity);
    });
    
    // Update orders
    data.orders.forEach((order: any) => {
      if (order.status === 'CANCELLED' || order.status === 'REJECTED') {
        this.ordersMap.delete(order.orderId);
      } else {
        this.ordersMap.set(order.orderId, order);
      }
    });
    
    this.emitUpdatedData();
    
    // Update portfolio if provided
    if (data.portfolio) {
      this.stateManager.updatePortfolioData(data.portfolio);
    }
  }

  private emitUpdatedData(): void {
    const equityArray = Array.from(this.equityDataMap.values());
    const ordersArray = Array.from(this.ordersMap.values());
    
    this.stateManager.updateEquityData(equityArray);
    this.stateManager.updateOrderData(ordersArray);
    
    this.logger.debug('📤 Emitted updated data', {
      equityCount: equityArray.length,
      orderCount: ordersArray.length
    });
  }

  public reset(): void {
    this.logger.info('🔄 Resetting exchange data handler');
    this.equityDataMap.clear();
    this.ordersMap.clear();
    this.sequenceNumber = 0;
    
    this.stateManager.updateEquityData([]);
    this.stateManager.updateOrderData([]);
  }
}