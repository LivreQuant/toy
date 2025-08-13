// src/stores/ExchangeDataStore.ts
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
  
  private constructor() {}
  
  public static getInstance(): ExchangeDataStore {
    if (!ExchangeDataStore.instance) {
      ExchangeDataStore.instance = new ExchangeDataStore();
    }
    return ExchangeDataStore.instance;
  }
  
  // Observable getters
  public getEquityData$(): Observable<EquityDataItem[]> {
    return this.equityDataSubject.asObservable();
  }
  
  public getOrders$(): Observable<OrderDataItem[]> {
    return this.ordersSubject.asObservable();
  }
  
  public getPortfolio$(): Observable<PortfolioData | null> {
    return this.portfolioSubject.asObservable();
  }
  
  public getLastUpdate$(): Observable<number> {
    return this.lastUpdateSubject.asObservable();
  }
  
  public getSequence$(): Observable<number> {
    return this.sequenceSubject.asObservable();
  }
  
  // Current state getters
  public getCurrentEquityData(): EquityDataItem[] {
    return this.equityDataSubject.value;
  }
  
  public getCurrentOrders(): OrderDataItem[] {
    return this.ordersSubject.value;
  }
  
  public getCurrentPortfolio(): PortfolioData | null {
    return this.portfolioSubject.value;
  }
  
  // Main update method
  public updateFromMessage(message: ExchangeDataMessage): void {
    logger.info('📊 Processing exchange data message', {
      deltaType: message.deltaType,
      sequence: message.sequence,
      equityCount: message.data.equityData.length,
      orderCount: message.data.orders.length,
      hasPortfolio: !!message.data.portfolio
    });
    
    // Validate sequence order (basic protection against out-of-order messages)
    const currentSequence = this.sequenceSubject.value;
    if (message.sequence <= currentSequence && message.deltaType === 'DELTA') {
      logger.warn('⚠️ Ignoring out-of-sequence delta message', {
        receivedSequence: message.sequence,
        currentSequence: currentSequence
      });
      return;
    }
    
    if (message.deltaType === 'FULL') {
      this.handleFullUpdate(message.data);
    } else if (message.deltaType === 'DELTA') {
      this.handleDeltaUpdate(message.data);
    }
    
    // Update sequence and timestamp
    this.sequenceSubject.next(message.sequence);
    this.lastUpdateSubject.next(message.timestamp);
  }
  
  private handleFullUpdate(data: ExchangeData): void {
    logger.info('🔄 Processing FULL update');
    
    // Clear existing data and rebuild from scratch
    this.equityDataMap.clear();
    this.ordersMap.clear();
    
    // Process equity data
    data.equityData.forEach(equity => {
      this.equityDataMap.set(equity.symbol, equity);
    });
    
    // Process orders
    data.orders.forEach(order => {
      this.ordersMap.set(order.orderId, order);
    });
    
    // Update portfolio directly (no delta logic needed)
    this.portfolioSubject.next(data.portfolio);
    
    // Emit updated arrays
    this.emitUpdatedData();
  }
  
  private handleDeltaUpdate(data: ExchangeData): void {
    logger.info('📊 Processing DELTA update', {
      equityUpdates: data.equityData.length,
      orderUpdates: data.orders.length
    });
    
    // Update equity data
    data.equityData.forEach(equity => {
      this.equityDataMap.set(equity.symbol, equity);
    });
    
    // Update orders
    data.orders.forEach(order => {
      if (order.status === 'CANCELLED' || order.status === 'REJECTED') {
        // Remove cancelled/rejected orders
        this.ordersMap.delete(order.orderId);
      } else {
        // Update or add order
        this.ordersMap.set(order.orderId, order);
      }
    });
    
    // Update portfolio if provided
    if (data.portfolio) {
      this.portfolioSubject.next(data.portfolio);
    }
    
    // Emit updated arrays
    this.emitUpdatedData();
  }
  
  private emitUpdatedData(): void {
    // Convert maps to arrays and emit
    const equityArray = Array.from(this.equityDataMap.values());
    const ordersArray = Array.from(this.ordersMap.values());
    
    this.equityDataSubject.next(equityArray);
    this.ordersSubject.next(ordersArray);
    
    logger.debug('📤 Emitted updated data', {
      equityCount: equityArray.length,
      orderCount: ordersArray.length
    });
  }
  
  // Reset method for disconnections
  public reset(): void {
    logger.info('🔄 Resetting exchange data store');
    this.equityDataMap.clear();
    this.ordersMap.clear();
    
    this.equityDataSubject.next([]);
    this.ordersSubject.next([]);
    this.portfolioSubject.next(null);
    this.lastUpdateSubject.next(0);
    this.sequenceSubject.next(0);
  }
}