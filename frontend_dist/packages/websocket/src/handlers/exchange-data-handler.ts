// frontend_dist/packages/websocket/src/handlers/exchange-data-handler.ts
import { getLogger } from '@trading-app/logging';

import { SocketClient } from '../client/socket-client';
import { ServerExchangeDataMessage, WebSocketMessage } from '../types/message-types';
import { StateManager } from '../types/connection-types';

// Global registry for additional exchange data handlers
interface ExchangeDataHandlerInterface {
  handleWebSocketMessage(message: any): boolean;
  handleDisconnection(): void;
}

class ExchangeDataHandlerRegistry {
  private handlers: ExchangeDataHandlerInterface[] = [];
  private logger = getLogger('ExchangeDataHandlerRegistry');
  
  register(handler: ExchangeDataHandlerInterface): void {
    this.handlers.push(handler);
    this.logger.info('🔧 REGISTRY: Handler registered', { 
      totalHandlers: this.handlers.length,
      handlerType: handler.constructor.name
    });
  }
  
  unregister(handler: ExchangeDataHandlerInterface): void {
    const index = this.handlers.indexOf(handler);
    if (index > -1) {
      this.handlers.splice(index, 1);
      this.logger.info('🔧 REGISTRY: Handler unregistered', { 
        totalHandlers: this.handlers.length,
        handlerType: handler.constructor.name
      });
    }
  }
  
  forwardMessage(message: any): void {
    this.logger.info('📡 REGISTRY: START - Forwarding message to registered handlers', { 
      handlerCount: this.handlers.length,
      messageType: message.type,
      deltaType: message.deltaType || 'N/A',
      sequence: message.sequence || 'N/A'
    });
    
    this.handlers.forEach((handler, index) => {
      try {
        this.logger.info(`📡 REGISTRY: Calling handler ${index} (${handler.constructor.name})`);
        const handled = handler.handleWebSocketMessage(message);
        this.logger.info(`📡 REGISTRY: Handler ${index} result: ${handled ? 'HANDLED' : 'NOT_HANDLED'}`);
      } catch (error: any) {
        this.logger.error(`❌ REGISTRY: Error in handler ${index}:`, {
          error: error.message,
          stack: error.stack,
          handlerType: handler.constructor.name
        });
      }
    });
    
    this.logger.info('📡 REGISTRY: END - Message forwarding complete');
  }
  
  notifyDisconnection(): void {
    this.logger.info('🔌 REGISTRY: Notifying all handlers of disconnection', { handlerCount: this.handlers.length });
    this.handlers.forEach((handler, index) => {
      try {
        this.logger.info(`🔌 REGISTRY: Notifying handler ${index} of disconnection`);
        handler.handleDisconnection();
        this.logger.info(`🔌 REGISTRY: Handler ${index} disconnection notification complete`);
      } catch (error: any) {
        this.logger.error(`❌ REGISTRY: Error notifying handler ${index} of disconnection:`, {
          error: error.message,
          handlerType: handler.constructor.name
        });
      }
    });
  }
}

// Export global registry
export const exchangeDataHandlerRegistry = new ExchangeDataHandlerRegistry();

export class ExchangeDataHandler {
  private logger = getLogger('ExchangeDataHandler');
  private sequenceNumber = 0;
  private equityDataMap = new Map<string, any>();
  private ordersMap = new Map<string, any>();
  
  constructor(private client: SocketClient, private stateManager: StateManager) {
    this.setupListeners();
    this.logger.info('🚀 HANDLER: ExchangeDataHandler initialized', {
      hasClient: !!client,
      hasStateManager: !!stateManager,
      stateManagerType: stateManager.constructor.name
    });
  }

  private setupListeners(): void {
    this.logger.info('🎧 HANDLER: Setting up WebSocket message listeners');
    this.client.on('message', (message: WebSocketMessage) => {
      this.logger.debug('📨 HANDLER: Received WebSocket message', { 
        type: message.type,
        hasData: !!(message as any).data // Type assertion for logging
      });
      
      if (message.type === 'exchange_data') {
        this.logger.info('📊 HANDLER: Identified exchange_data message - processing...');
        this.handleExchangeData(message as ServerExchangeDataMessage);
      } else {
        this.logger.debug('📨 HANDLER: Ignoring non-exchange_data message', { type: message.type });
      }
    });
    this.logger.info('🎧 HANDLER: WebSocket listeners setup complete');
  }


  private handleExchangeData(message: ServerExchangeDataMessage): void {
    // FIXED: Handle missing fields gracefully
    const equityCount = message.data.equityData?.length || 0;
    const orderCount = message.data.orders?.length || 0;
    const hasPortfolio = !!message.data.portfolio;
  
    this.logger.info('📊 HANDLER: START - Processing exchange_data message', {
      deltaType: message.deltaType,
      sequence: message.sequence,
      timestamp: message.timestamp,
      compressed: message.compressed,
      equityCount,
      orderCount,
      hasPortfolio,
      currentSequence: this.sequenceNumber
    });
    
    // Log detailed equity data
    if (equityCount > 0) {
      this.logger.info('📊 HANDLER: Equity data details', {
        symbols: message.data.equityData.map(e => e.symbol),
        firstEquity: message.data.equityData[0],
        samplePrices: message.data.equityData.slice(0, 3).map(e => `${e.symbol}:${e.close}`)
      });
    }
    
    // STEP 1: Forward to registered handlers FIRST (including ExchangeDataStore)
    this.logger.info('📡 HANDLER: STEP 1 - Forwarding to registered handlers...');
    exchangeDataHandlerRegistry.forwardMessage(message);
    this.logger.info('📡 HANDLER: STEP 1 COMPLETE - Handler forwarding done');
    
    // STEP 2: Validate sequence for delta messages
    if (message.deltaType === 'DELTA' && message.sequence <= this.sequenceNumber) {
      this.logger.warn('⚠️ HANDLER: REJECTED - Out-of-sequence delta message', {
        receivedSequence: message.sequence,
        currentSequence: this.sequenceNumber,
        action: 'IGNORING_MESSAGE'
      });
      return;
    }
    
    // STEP 3: Process message based on type
    this.logger.info('📊 HANDLER: STEP 2 - Processing message for global state...', {
      deltaType: message.deltaType
    });
    
    if (message.deltaType === 'FULL') {
      this.logger.info('🔄 HANDLER: Processing as FULL update');
      this.handleFullUpdate(message.data);
    } else if (message.deltaType === 'DELTA') {
      this.logger.info('📊 HANDLER: Processing as DELTA update');
      this.handleDeltaUpdate(message.data);
    }
    
    // STEP 4: Update sequence
    const oldSequence = this.sequenceNumber;
    this.sequenceNumber = message.sequence;
    
    this.logger.info('✅ HANDLER: END - Exchange data processing complete', { 
      oldSequence,
      newSequence: this.sequenceNumber,
      totalEquityCount: this.equityDataMap.size,
      totalOrderCount: this.ordersMap.size
    });
  }

  private handleFullUpdate(data: any): void {
    this.logger.info('🔄 HANDLER: FULL UPDATE START - Rebuilding all data from scratch');
    
    // Clear and rebuild equity data
    const oldEquityCount = this.equityDataMap.size;
    this.equityDataMap.clear();
    
    this.logger.info('🔄 HANDLER: Processing equity data for FULL update', {
      oldCount: oldEquityCount,
      newCount: data.equityData?.length || 0
    });
    
    // FIXED: Handle missing equityData
    if (data.equityData) {
      data.equityData.forEach((equity: any, index: number) => {
        this.equityDataMap.set(equity.symbol, equity);
        if (index < 3) { // Log first 3 for debugging
          this.logger.debug(`🔄 HANDLER: Added equity ${index + 1}:`, {
            symbol: equity.symbol,
            close: equity.close,
            volume: equity.volume,
            exchange: equity.exchange_type
          });
        }
      });
    }
    
    // Clear and rebuild orders
    const oldOrderCount = this.ordersMap.size;
    this.ordersMap.clear();
    
    this.logger.info('🔄 HANDLER: Processing orders for FULL update', {
      oldCount: oldOrderCount,
      newCount: data.orders?.length || 0
    });
    
    // FIXED: Handle missing orders
    if (data.orders) {
      data.orders.forEach((order: any) => {
        this.ordersMap.set(order.orderId, order);
      });
    }
    
    // STEP: Update global state
    this.logger.info('📤 HANDLER: FULL UPDATE - Pushing data to global state...');
    this.emitUpdatedData();
    
    // Update portfolio directly if provided
    if (data.portfolio) {
      this.logger.info('💰 HANDLER: FULL UPDATE - Updating portfolio data', {
        cashBalance: data.portfolio.cash_balance,
        totalValue: data.portfolio.total_value,
        positionCount: data.portfolio.positions?.length || 0
      });
      this.stateManager.updatePortfolioData(data.portfolio);
    } else {
      this.logger.info('💰 HANDLER: FULL UPDATE - No portfolio data in message');
    }
    
    this.logger.info('✅ HANDLER: FULL UPDATE COMPLETE');
  }

  private handleDeltaUpdate(data: any): void {
    this.logger.info('📊 HANDLER: DELTA UPDATE START', {
      equityUpdates: data.equityData?.length || 0,
      orderUpdates: data.orders?.length || 0,
      beforeEquityCount: this.equityDataMap.size,
      beforeOrderCount: this.ordersMap.size
    });
    
    // Update equity data
    let equityUpdatedCount = 0;
    let equityAddedCount = 0;
    
    // FIXED: Handle missing equityData in DELTA
    if (data.equityData && data.equityData.length > 0) {
      data.equityData.forEach((equity: any) => {
        const existed = this.equityDataMap.has(equity.symbol);
        this.equityDataMap.set(equity.symbol, equity);
        
        if (existed) {
          equityUpdatedCount++;
          this.logger.debug(`📊 HANDLER: DELTA - Updated equity: ${equity.symbol} = ${equity.close}`);
        } else {
          equityAddedCount++;
          this.logger.debug(`📊 HANDLER: DELTA - Added new equity: ${equity.symbol} = ${equity.close}`);
        }
      });
    }
    
    this.logger.info('📊 HANDLER: DELTA - Equity processing complete', {
      updated: equityUpdatedCount,
      added: equityAddedCount,
      total: this.equityDataMap.size
    });
    
    // Update orders
    let orderUpdatedCount = 0;
    let orderAddedCount = 0;
    let orderRemovedCount = 0;
    
    // FIXED: Handle missing orders in DELTA
    if (data.orders && data.orders.length > 0) {
      data.orders.forEach((order: any) => {
        if (order.status === 'CANCELLED' || order.status === 'REJECTED') {
          const existed = this.ordersMap.has(order.orderId);
          this.ordersMap.delete(order.orderId);
          if (existed) {
            orderRemovedCount++;
            this.logger.debug(`📊 HANDLER: DELTA - Removed order: ${order.orderId} (${order.status})`);
          }
        } else {
          const existed = this.ordersMap.has(order.orderId);
          this.ordersMap.set(order.orderId, order);
          
          if (existed) {
            orderUpdatedCount++;
            this.logger.debug(`📊 HANDLER: DELTA - Updated order: ${order.orderId}`);
          } else {
            orderAddedCount++;
            this.logger.debug(`📊 HANDLER: DELTA - Added new order: ${order.orderId}`);
          }
        }
      });
    }
    
    this.logger.info('📊 HANDLER: DELTA - Order processing complete', {
      updated: orderUpdatedCount,
      added: orderAddedCount,
      removed: orderRemovedCount,
      total: this.ordersMap.size
    });
    
    // STEP: Update global state
    this.logger.info('📤 HANDLER: DELTA UPDATE - Pushing data to global state...');
    this.emitUpdatedData();
    
    // Update portfolio if provided
    if (data.portfolio) {
      this.logger.info('💰 HANDLER: DELTA UPDATE - Updating portfolio data', {
        cashBalance: data.portfolio.cash_balance,
        totalValue: data.portfolio.total_value,
        positionCount: data.portfolio.positions?.length || 0
      });
      this.stateManager.updatePortfolioData(data.portfolio);
    } else {
      this.logger.debug('💰 HANDLER: DELTA UPDATE - No portfolio data in message');
    }
    
    this.logger.info('✅ HANDLER: DELTA UPDATE COMPLETE');
  }

  private emitUpdatedData(): void {
    const equityArray = Array.from(this.equityDataMap.values());
    const ordersArray = Array.from(this.ordersMap.values());
    
    this.logger.info('📤 HANDLER: EMIT START - Sending data to global state', {
      equityCount: equityArray.length,
      orderCount: ordersArray.length,
      equitySymbols: equityArray.map(e => e.symbol).slice(0, 5), // First 5 symbols
      sampleEquityPrices: equityArray.slice(0, 3).map(e => `${e.symbol}:${e.close}`)
    });
    
    // Push to global state manager
    this.logger.info('📤 HANDLER: Calling stateManager.updateEquityData...');
    this.stateManager.updateEquityData(equityArray);
    this.logger.info('📤 HANDLER: stateManager.updateEquityData COMPLETE');
    
    this.logger.info('📤 HANDLER: Calling stateManager.updateOrderData...');
    this.stateManager.updateOrderData(ordersArray);
    this.logger.info('📤 HANDLER: stateManager.updateOrderData COMPLETE');
    
    this.logger.info('✅ HANDLER: EMIT COMPLETE - Data successfully pushed to global state');
  }

  public reset(): void {
    this.logger.info('🔄 HANDLER: RESET START - Clearing all data');
    
    const beforeEquityCount = this.equityDataMap.size;
    const beforeOrderCount = this.ordersMap.size;
    const beforeSequence = this.sequenceNumber;
    
    this.equityDataMap.clear();
    this.ordersMap.clear();
    this.sequenceNumber = 0;
    
    // Notify registered handlers of disconnection
    this.logger.info('🔌 HANDLER: Notifying registered handlers of reset...');
    exchangeDataHandlerRegistry.notifyDisconnection();
    
    // Clear global state
    this.logger.info('📤 HANDLER: Clearing global state...');
    this.stateManager.updateEquityData([]);
    this.stateManager.updateOrderData([]);
    
    this.logger.info('✅ HANDLER: RESET COMPLETE', {
      clearedEquityCount: beforeEquityCount,
      clearedOrderCount: beforeOrderCount,
      resetSequenceFrom: beforeSequence
    });
  }

  // Debug method to check current state
  public getDebugInfo(): any {
    const debugInfo = {
      sequenceNumber: this.sequenceNumber,
      equityCount: this.equityDataMap.size,
      orderCount: this.ordersMap.size,
      equitySymbols: Array.from(this.equityDataMap.keys()),
      orderIds: Array.from(this.ordersMap.keys()),
      sampleEquityData: Array.from(this.equityDataMap.values()).slice(0, 2)
    };
    
    this.logger.info('🔍 HANDLER: Debug info requested', debugInfo);
    return debugInfo;
  }
}