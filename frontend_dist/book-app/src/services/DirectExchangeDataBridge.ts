// frontend_dist/book-app/src/services/DirectExchangeDataBridge.ts
import { getLogger } from '@trading-app/logging';
import { ExchangeDataStore } from '../stores/ExchangeDataStore';

const logger = getLogger('DirectExchangeDataBridge');

export function initializeDirectDataBridge() {
  logger.info('🚀 Setting up direct exchange data bridge');
  
  // Find the socket client that's already receiving messages
  const findSocketClient = () => {
    // The socket client is probably on the window object or in a global
    if ((window as any).serviceManager) {
      const connectionManager = (window as any).serviceManager.getConnectionManager();
      if (connectionManager && (connectionManager as any).socketClient) {
        return (connectionManager as any).socketClient;
      }
    }
    
    // Alternative: check if it's stored elsewhere
    if ((window as any).socketClient) {
      return (window as any).socketClient;
    }
    
    return null;
  };

  const socketClient = findSocketClient();
  
  if (!socketClient) {
    logger.error('🚀 No socket client found - will try again in 2 seconds');
    setTimeout(initializeDirectDataBridge, 2000);
    return;
  }

  logger.info('🚀 Found socket client, setting up message listener');
  
  const store = ExchangeDataStore.getInstance();
  
  // Listen for messages and forward exchange_data directly to the store
  socketClient.on('message', (message: any) => {
    if (message.type === 'exchange_data') {
      logger.info('🚀 Got exchange_data, forwarding to store', {
        equityCount: message.data?.equityData?.length || 0
      });
      
      try {
        store.updateFromMessage(message);
        logger.info('🚀 Successfully updated store with exchange data');
      } catch (error: any) {
        logger.error('🚀 Error updating store:', error.message);
      }
    }
  });

  logger.info('🚀 Direct bridge setup complete - exchange data will now flow to dashboards');
}