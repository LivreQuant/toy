// frontend_dist/book-app/src/stores/ExchangeDataStore.ts
import { BehaviorSubject, Observable } from 'rxjs';
import { getLogger } from '@trading-app/logging';
import { 
  ExchangeDataMessage, 
  ExchangeData, 
  EquityDataItem, 
  OrderDataItem, 
  PortfolioData 
} from '../types/ExchangeData';

const logger = getLogger('ExchangeDataStore');

export class ExchangeDataStore {
  private static instance: ExchangeDataStore;
  
  // Current state subjects
  private equityDataSubject = new BehaviorSubject<EquityDataItem[]>([]);
  private ordersSubject = new BehaviorSubject<OrderDataItem[]>([]);
  private portfolioSubject = new BehaviorSubject<PortfolioData | null>(null);
  private lastUpdateSubject = new BehaviorSubject<number>(0);
  private sequenceSubject = new BehaviorSubject<number>(0);
  
  // Current state maps for efficient delta updates
  private equityDataMap = new Map<string, EquityDataItem>();
  private ordersMap = new Map<string, OrderDataItem>();
  
  private constructor() {
    logger.info('🏪 STORE: ExchangeDataStore singleton instance created');
    
    // Add logging for subscriber counts
    this.equityDataSubject.subscribe(() => {
      logger.debug('🏪 STORE: Equity data subject emitted to subscribers', {
        subscriberCount: (this.equityDataSubject as any).observers?.length || 'unknown'
      });
    });
  }
  
  public static getInstance(): ExchangeDataStore {
    if (!ExchangeDataStore.instance) {
      logger.info('🏪 STORE: Creating new ExchangeDataStore instance');
      ExchangeDataStore.instance = new ExchangeDataStore();
    } else {
      logger.debug('🏪 STORE: Returning existing ExchangeDataStore instance');
    }
    return ExchangeDataStore.instance;
  }
  
  // Observable getters with logging
  public getEquityData$(): Observable<EquityDataItem[]> {
    logger.debug('🏪 STORE: getEquityData$() called - returning observable', {
      currentDataCount: this.equityDataSubject.value.length
    });
    return this.equityDataSubject.asObservable();
  }
  
  public getOrders$(): Observable<OrderDataItem[]> {
    logger.debug('🏪 STORE: getOrders$() called - returning observable');
    return this.ordersSubject.asObservable();
  }
  
  public getPortfolio$(): Observable<PortfolioData | null> {
    logger.debug('🏪 STORE: getPortfolio$() called - returning observable');
    return this.portfolioSubject.asObservable();
  }
  
  public getLastUpdate$(): Observable<number> {
    return this.lastUpdateSubject.asObservable();
  }
  
  public getSequence$(): Observable<number> {
    return this.sequenceSubject.asObservable();
  }
  
  // Current state getters with logging
  public getCurrentEquityData(): EquityDataItem[] {
    const currentData = this.equityDataSubject.value;
    logger.debug('🏪 STORE: getCurrentEquityData() called', {
      count: currentData.length,
      symbols: currentData.map(e => e.symbol).slice(0, 5)
    });
    return currentData;
  }
  
  public getCurrentOrders(): OrderDataItem[] {
    const currentOrders = this.ordersSubject.value;
    logger.debug('🏪 STORE: getCurrentOrders() called', { count: currentOrders.length });
    return currentOrders;
  }
  
  public getCurrentPortfolio(): PortfolioData | null {
    const currentPortfolio = this.portfolioSubject.value;
    logger.debug('🏪 STORE: getCurrentPortfolio() called', { hasPortfolio: !!currentPortfolio });
    return currentPortfolio;
  }
  
  // Main update method with comprehensive logging
  public updateFromMessage(message: ExchangeDataMessage): void {
    logger.info('🏪 STORE: UPDATE START - Processing exchange data message', {
      deltaType: message.deltaType,
      sequence: message.sequence,
      timestamp: message.timestamp,
      compressed: message.compressed,
      equityCount: message.data.equityData.length,
      orderCount: message.data.orders.length,
      hasPortfolio: !!message.data.portfolio,
      currentSequence: this.sequenceSubject.value,
      currentEquityCount: this.equityDataMap.size,
      currentOrderCount: this.ordersMap.size
    });
    
    // Log sample equity data
    if (message.data.equityData.length > 0) {
      logger.info('🏪 STORE: Sample equity data from message', {
        sampleEquities: message.data.equityData.slice(0, 3).map(e => ({
          symbol: e.symbol,
          close: e.close,
          volume: e.volume,
          exchange: e.exchange_type
        }))
      });
    }
    
    // Validate sequence order (basic protection against out-of-order messages)
    const currentSequence = this.sequenceSubject.value;
    if (message.sequence <= currentSequence && message.deltaType === 'DELTA') {
      logger.warn('⚠️ STORE: REJECTED - Out-of-sequence delta message', {
        receivedSequence: message.sequence,
        currentSequence: currentSequence,
        action: 'IGNORING_MESSAGE'
     });
     return;
   }
   
   if (message.deltaType === 'FULL') {
     logger.info('🏪 STORE: Processing as FULL update');
     this.handleFullUpdate(message.data);
   } else if (message.deltaType === 'DELTA') {
     logger.info('🏪 STORE: Processing as DELTA update');
     this.handleDeltaUpdate(message.data);
   }
   
   // Update sequence and timestamp
   const oldSequence = this.sequenceSubject.value;
   const oldTimestamp = this.lastUpdateSubject.value;
   
   this.sequenceSubject.next(message.sequence);
   this.lastUpdateSubject.next(message.timestamp);
   
   logger.info('✅ STORE: UPDATE COMPLETE - Exchange data store update finished', {
     oldSequence,
     newSequence: message.sequence,
     oldTimestamp,
     newTimestamp: message.timestamp,
     finalEquityCount: this.equityDataMap.size,
     finalOrderCount: this.ordersMap.size
   });
 }
 
 private handleFullUpdate(data: ExchangeData): void {
   logger.info('🏪 STORE: FULL UPDATE START - Rebuilding all data from scratch');
   
   // Log before state
   const beforeEquityCount = this.equityDataMap.size;
   const beforeOrderCount = this.ordersMap.size;
   const beforeSymbols = Array.from(this.equityDataMap.keys()).slice(0, 5);
   
   logger.info('🏪 STORE: Before FULL update state', {
     beforeEquityCount,
     beforeOrderCount,
     beforeSymbols
   });
   
   // Clear existing data and rebuild from scratch
   this.equityDataMap.clear();
   this.ordersMap.clear();
   
   logger.info('🏪 STORE: Cleared existing data, processing new equity data...');
   
   // Process equity data
   data.equityData.forEach((equity, index) => {
     this.equityDataMap.set(equity.symbol, equity);
     if (index < 3) { // Log first 3 for debugging
       logger.debug(`🏪 STORE: FULL - Added equity ${index + 1}:`, {
         symbol: equity.symbol,
         close: equity.close,
         volume: equity.volume,
         exchange: equity.exchange_type
       });
     }
   });
   
   logger.info('🏪 STORE: Equity data processing complete, processing orders...');
   
   // Process orders
   data.orders.forEach((order, index) => {
     this.ordersMap.set(order.orderId, order);
     if (index < 3) { // Log first 3 for debugging
       logger.debug(`🏪 STORE: FULL - Added order ${index + 1}:`, {
         orderId: order.orderId,
         symbol: order.symbol,
         status: order.status
       });
     }
   });
   
   logger.info('🏪 STORE: Order data processing complete, updating portfolio...');
   
   // Update portfolio directly (no delta logic needed)
   if (data.portfolio) {
     logger.info('🏪 STORE: FULL - Updating portfolio data', {
       cashBalance: data.portfolio.cash_balance,
       totalValue: data.portfolio.total_value,
       positionCount: data.portfolio.positions?.length || 0
     });
     this.portfolioSubject.next(data.portfolio);
   } else {
     logger.info('🏪 STORE: FULL - No portfolio data in message');
     this.portfolioSubject.next(null);
   }
   
   // Emit updated arrays
   logger.info('🏪 STORE: FULL - Emitting updated data to subscribers...');
   this.emitUpdatedData();
   
   logger.info('✅ STORE: FULL UPDATE COMPLETE', {
     finalEquityCount: this.equityDataMap.size,
     finalOrderCount: this.ordersMap.size,
     newSymbols: Array.from(this.equityDataMap.keys()).slice(0, 5)
   });
 }
 
 private handleDeltaUpdate(data: ExchangeData): void {
   logger.info('🏪 STORE: DELTA UPDATE START', {
     equityUpdates: data.equityData.length,
     orderUpdates: data.orders.length,
     beforeEquityCount: this.equityDataMap.size,
     beforeOrderCount: this.ordersMap.size
   });
   
   // Update equity data
   let equityUpdatedCount = 0;
   let equityAddedCount = 0;
   
   logger.info('🏪 STORE: DELTA - Processing equity updates...');
   data.equityData.forEach((equity, index) => {
     const existed = this.equityDataMap.has(equity.symbol);
     this.equityDataMap.set(equity.symbol, equity);
     
     if (existed) {
       equityUpdatedCount++;
       if (index < 3) { // Log first 3 updates
         logger.debug(`🏪 STORE: DELTA - Updated equity: ${equity.symbol} = ${equity.close}`);
       }
     } else {
       equityAddedCount++;
       if (index < 3) { // Log first 3 additions
         logger.debug(`🏪 STORE: DELTA - Added new equity: ${equity.symbol} = ${equity.close}`);
       }
     }
   });
   
   logger.info('🏪 STORE: DELTA - Equity processing complete', {
     updated: equityUpdatedCount,
     added: equityAddedCount,
     total: this.equityDataMap.size
   });
   
   // Update orders
   let orderUpdatedCount = 0;
   let orderAddedCount = 0;
   let orderRemovedCount = 0;
   
   logger.info('🏪 STORE: DELTA - Processing order updates...');
   data.orders.forEach((order, index) => {
     if (order.status === 'CANCELLED' || order.status === 'REJECTED') {
       const existed = this.ordersMap.has(order.orderId);
       this.ordersMap.delete(order.orderId);
       if (existed) {
         orderRemovedCount++;
         if (index < 3) {
           logger.debug(`🏪 STORE: DELTA - Removed order: ${order.orderId} (${order.status})`);
         }
       }
     } else {
       const existed = this.ordersMap.has(order.orderId);
       this.ordersMap.set(order.orderId, order);
       
       if (existed) {
         orderUpdatedCount++;
         if (index < 3) {
           logger.debug(`🏪 STORE: DELTA - Updated order: ${order.orderId}`);
         }
       } else {
         orderAddedCount++;
         if (index < 3) {
           logger.debug(`🏪 STORE: DELTA - Added new order: ${order.orderId}`);
         }
       }
     }
   });
   
   logger.info('🏪 STORE: DELTA - Order processing complete', {
     updated: orderUpdatedCount,
     added: orderAddedCount,
     removed: orderRemovedCount,
     total: this.ordersMap.size
   });
   
   // Update portfolio if provided
   if (data.portfolio) {
     logger.info('🏪 STORE: DELTA - Updating portfolio data', {
       cashBalance: data.portfolio.cash_balance,
       totalValue: data.portfolio.total_value,
       positionCount: data.portfolio.positions?.length || 0
     });
     this.portfolioSubject.next(data.portfolio);
   } else {
     logger.debug('🏪 STORE: DELTA - No portfolio data in message');
   }
   
   // Emit updated arrays
   logger.info('🏪 STORE: DELTA - Emitting updated data to subscribers...');
   this.emitUpdatedData();
   
   logger.info('✅ STORE: DELTA UPDATE COMPLETE');
 }
 
 private emitUpdatedData(): void {
   // Convert maps to arrays and emit
   const equityArray = Array.from(this.equityDataMap.values());
   const ordersArray = Array.from(this.ordersMap.values());
   
   logger.info('🏪 STORE: EMIT START - Converting maps to arrays and emitting', {
     equityArrayLength: equityArray.length,
     ordersArrayLength: ordersArray.length,
     sampleEquities: equityArray.slice(0, 3).map(e => `${e.symbol}:${e.close}`),
     subscriberInfo: 'Emitting to all subscribers...'
   });
   
   // Emit equity data
   logger.info('🏪 STORE: Emitting equity data to equityDataSubject...');
   this.equityDataSubject.next(equityArray);
   logger.info('✅ STORE: Equity data emitted successfully');
   
   // Emit orders data
   logger.info('🏪 STORE: Emitting orders data to ordersSubject...');
   this.ordersSubject.next(ordersArray);
   logger.info('✅ STORE: Orders data emitted successfully');
   
   logger.info('✅ STORE: EMIT COMPLETE - All data emitted to subscribers', {
     finalEquityCount: equityArray.length,
     finalOrderCount: ordersArray.length
   });
 }
 
 // Reset method for disconnections
 public reset(): void {
   logger.info('🏪 STORE: RESET START - Clearing all data due to disconnection');
   
   const beforeEquityCount = this.equityDataMap.size;
   const beforeOrderCount = this.ordersMap.size;
   const beforeSequence = this.sequenceSubject.value;
   
   this.equityDataMap.clear();
   this.ordersMap.clear();
   
   logger.info('🏪 STORE: Maps cleared, emitting empty data...');
   
   this.equityDataSubject.next([]);
   this.ordersSubject.next([]);
   this.portfolioSubject.next(null);
   this.lastUpdateSubject.next(0);
   this.sequenceSubject.next(0);
   
   logger.info('✅ STORE: RESET COMPLETE', {
     clearedEquityCount: beforeEquityCount,
     clearedOrderCount: beforeOrderCount,
     resetSequenceFrom: beforeSequence
   });
 }
 
 // Debug method
 public getDebugInfo(): any {
   const debugInfo = {
     equityCount: this.equityDataMap.size,
     orderCount: this.ordersMap.size,
     currentSequence: this.sequenceSubject.value,
     lastUpdate: this.lastUpdateSubject.value,
     equitySymbols: Array.from(this.equityDataMap.keys()).slice(0, 10),
     sampleEquityData: Array.from(this.equityDataMap.values()).slice(0, 2),
     hasPortfolio: !!this.portfolioSubject.value
   };
   
   logger.info('🏪 STORE: Debug info requested', debugInfo);
   return debugInfo;
 }
}