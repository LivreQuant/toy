// frontend_dist/book-app/src/services/ExchangeDataHandler.ts
import { getLogger } from '@trading-app/logging';
import { ExchangeDataStore } from '../stores/ExchangeDataStore';
import { ExchangeDataMessage } from '../types/ExchangeData';

// Import the registry from the websocket package
import { exchangeDataHandlerRegistry } from '@trading-app/websocket';

const logger = getLogger('BookApp_ExchangeDataHandler');

export class ExchangeDataHandler {
  private store: ExchangeDataStore;
  
  constructor() {
    logger.info('📱 BOOK_HANDLER: Initializing BookApp ExchangeDataHandler');
    
    this.store = ExchangeDataStore.getInstance();
    logger.info('📱 BOOK_HANDLER: Got ExchangeDataStore instance', {
      hasStore: !!this.store
    });
    
    // Register this handler with the websocket package
    logger.info('📱 BOOK_HANDLER: Registering with websocket package registry...');
    exchangeDataHandlerRegistry.register(this);
    logger.info('✅ BOOK_HANDLER: Successfully registered with websocket package');
  }
  
  public handleWebSocketMessage(message: any): boolean {
    logger.info('📱 BOOK_HANDLER: handleWebSocketMessage CALLED', {
      messageType: message?.type,
      hasDeltaType: !!message?.deltaType,
      hasData: !!message?.data
    });
    
    try {
      // Check if this is an exchange_data message
      if (message.type === 'exchange_data') {
        const exchangeMessage = message as ExchangeDataMessage;
        
        // FIXED: Handle missing fields gracefully
        const equityCount = exchangeMessage.data.equityData?.length || 0;
        const orderCount = exchangeMessage.data.orders?.length || 0;
        const hasPortfolio = !!exchangeMessage.data.portfolio;
        
        logger.info('📱 BOOK_HANDLER: Processing exchange_data message', {
          deltaType: exchangeMessage.deltaType,
          sequence: exchangeMessage.sequence,
          timestamp: exchangeMessage.timestamp,
          compressed: exchangeMessage.compressed,
          equityCount,
          orderCount,
          hasPortfolio
        });
        
        // Log sample equity data if available
        if (equityCount > 0) {
          logger.info('📱 BOOK_HANDLER: Sample equity data', {
            sampleEquities: exchangeMessage.data.equityData.slice(0, 3).map(e => ({
              symbol: e.symbol,
              close: e.close,
              volume: e.volume
            }))
          });
        }
        
        logger.info('📱 BOOK_HANDLER: Calling store.updateFromMessage...');
        this.store.updateFromMessage(exchangeMessage);
        logger.info('✅ BOOK_HANDLER: store.updateFromMessage COMPLETE');
        
        // Verify the store was updated
        const currentData = this.store.getCurrentEquityData();
        logger.info('📱 BOOK_HANDLER: Store verification after update', {
          currentEquityCount: currentData.length,
          currentSymbols: currentData.map(e => e.symbol).slice(0, 5)
        });
        
        return true; // Message was handled
      } else {
        logger.debug('📱 BOOK_HANDLER: Not an exchange_data message', {
          messageType: message?.type
        });
        return false; // Message not handled by this handler
      }
    } catch (error: any) {
      logger.error('❌ BOOK_HANDLER: Error processing exchange_data message', {
        error: error.message,
        stack: error.stack,
        messageType: message?.type
      });
      return false;
    }
  }
  
  public handleDisconnection(): void {
    logger.info('🔌 BOOK_HANDLER: Connection lost - resetting exchange data');
    try {
      this.store.reset();
      logger.info('✅ BOOK_HANDLER: Store reset complete');
    } catch (error: any) {
      logger.error('❌ BOOK_HANDLER: Error during disconnection handling', {
        error: error.message
      });
    }
  }
  
  public dispose(): void {
    logger.info('📱 BOOK_HANDLER: Disposing handler...');
    try {
      // Unregister when disposing
      exchangeDataHandlerRegistry.unregister(this);
      logger.info('✅ BOOK_HANDLER: Successfully unregistered from websocket package');
    } catch (error: any) {
      logger.error('❌ BOOK_HANDLER: Error during disposal', {
        error: error.message
      });
    }
  }
  
  // Debug method
  public getDebugInfo(): any {
    const debugInfo = {
      hasStore: !!this.store,
      storeData: this.store ? this.store.getDebugInfo() : null
    };
    
    logger.info('📱 BOOK_HANDLER: Debug info requested', debugInfo);
    return debugInfo;
  }
}