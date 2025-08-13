// src/services/ExchangeDataHandler.ts
import { getLogger } from '@trading-app/logging';
import { ExchangeDataStore } from '../stores/ExchangeDataStore';
import { ExchangeDataMessage } from '../types/ExchangeData';

const logger = getLogger('ExchangeDataHandler');

export class ExchangeDataHandler {
  private store: ExchangeDataStore;
  
  constructor() {
    this.store = ExchangeDataStore.getInstance();
  }
  
  public handleWebSocketMessage(message: any): boolean {
    try {
      // Check if this is an exchange_data message
      if (message.type === 'exchange_data') {
        const exchangeMessage = message as ExchangeDataMessage;
        
        logger.info('📨 Received exchange_data message', {
          deltaType: exchangeMessage.deltaType,
          sequence: exchangeMessage.sequence,
          timestamp: exchangeMessage.timestamp,
          compressed: exchangeMessage.compressed
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
}