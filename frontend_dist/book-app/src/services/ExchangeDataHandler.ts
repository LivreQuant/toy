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
    this.store = ExchangeDataStore.getInstance();
    
    // ✅ FIX: Register this handler with the websocket package
    exchangeDataHandlerRegistry.register(this);
    logger.info('📱 Book app exchange data handler registered with websocket package');
  }
  
  public handleWebSocketMessage(message: any): boolean {
    try {
      // Check if this is an exchange_data message
      if (message.type === 'exchange_data') {
        const exchangeMessage = message as ExchangeDataMessage;
        
        logger.info('📨 Received exchange_data message in book app', {
          deltaType: exchangeMessage.deltaType,
          sequence: exchangeMessage.sequence,
          timestamp: exchangeMessage.timestamp,
          compressed: exchangeMessage.compressed,
          equityCount: exchangeMessage.data.equityData.length
        });
        
        this.store.updateFromMessage(exchangeMessage);
        return true; // Message was handled
      }
      
      return false; // Message not handled by this handler
    } catch (error: any) {
      logger.error('❌ Error processing exchange_data message', {
        error: error.message,
        messageType: message?.type
      });
      return false;
    }
  }
  
  public handleDisconnection(): void {
    logger.info('🔌 Connection lost - resetting exchange data');
    this.store.reset();
  }
  
  public dispose(): void {
    // ✅ FIX: Unregister when disposing
    exchangeDataHandlerRegistry.unregister(this);
    logger.info('📱 Book app exchange data handler unregistered');
  }
}