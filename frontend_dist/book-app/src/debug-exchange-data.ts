// frontend_dist/book-app/src/debug-exchange-data.ts
import { getLogger } from '@trading-app/logging';

const logger = getLogger('ExchangeDataDebug');

export function debugExchangeDataFlow() {
  logger.info('🔍 STARTING EXCHANGE DATA FLOW DEBUG');
  
  // 1. Find and hook into the socket client that's receiving messages
  const findAndHookSocket = () => {
    // Check window.serviceManager
    if ((window as any).serviceManager) {
      const sm = (window as any).serviceManager;
      logger.info('🔍 Found serviceManager on window');
      
      const connectionManager = sm.getConnectionManager();
      if (connectionManager) {
        logger.info('🔍 Found connectionManager');
        
        const socketClient = (connectionManager as any).socketClient;
        if (socketClient) {
          logger.info('🔍 Found socketClient on connectionManager');
          
          // Hook into the message handler
          const originalOn = socketClient.on;
          socketClient.on = function(event: string, callback: Function) {
            if (event === 'message') {
              logger.info('🔍 Someone is listening for socket messages');
              
              // Wrap the callback to log messages
              const wrappedCallback = function(message: any) {
                if (message.type === 'exchange_data') {
                  logger.info('🔍 EXCHANGE_DATA MESSAGE INTERCEPTED', {
                    type: message.type,
                    sequence: message.sequence,
                    equityCount: message.data?.equityData?.length || 0,
                    rawData: message.data?.equityData
                  });
                }
                return callback(message);
              };
              
              return originalOn.call(this, event, wrappedCallback);
            }
            return originalOn.call(this, event, callback);
          };
          
          logger.info('🔍 Socket message handler hooked');
          return true;
        }
      }
    }
    
    // Check other possible locations
    const globalKeys = Object.keys(window as any).filter(key => 
      key.toLowerCase().includes('socket') || 
      key.toLowerCase().includes('connection')
    );
    
    logger.info('🔍 Global keys containing socket/connection:', globalKeys);
    
    return false;
  };
  
  // 2. Hook into ExchangeDataStore
  const hookStore = () => {
    try {
      // Use dynamic import instead of require
      import('./stores/ExchangeDataStore').then((module) => {
        const store = module.ExchangeDataStore.getInstance();
        
        logger.info('🔍 Found ExchangeDataStore');
        
        // Hook updateFromMessage
        const originalUpdate = store.updateFromMessage;
        store.updateFromMessage = function(message: any) {
          logger.info('🔍 ExchangeDataStore.updateFromMessage CALLED', {
            deltaType: message.deltaType,
            sequence: message.sequence,
            equityCount: message.data?.equityData?.length || 0
          });
          
          const result = originalUpdate.call(this, message);
          
          logger.info('🔍 ExchangeDataStore updated, current equity data:', {
            currentEquityCount: this.getCurrentEquityData().length,
            equityData: this.getCurrentEquityData()
          });
          
          return result;
        };
        
        logger.info('🔍 ExchangeDataStore hooked');
      }).catch((error: any) => {
        logger.error('🔍 Error importing ExchangeDataStore:', error.message);
      });
      
      return true;
    } catch (error: any) {
      logger.error('🔍 Error hooking ExchangeDataStore:', error.message);
      return false;
    }
  };
  
  // 3. Hook into useMarketData (if we can find it)
  const hookMarketDataHook = () => {
    logger.info('🔍 Market data hook will be traced when components mount');
  };
  
  if (findAndHookSocket()) {
    logger.info('🔍 ✅ Socket hooked successfully');
  } else {
    logger.error('🔍 ❌ Failed to hook socket');
  }
  
  if (hookStore()) {
    logger.info('🔍 ✅ Store hooked successfully');
  } else {
    logger.error('🔍 ❌ Failed to hook store');
  }
  
  hookMarketDataHook();
  
  logger.info('🔍 EXCHANGE DATA FLOW DEBUG SETUP COMPLETE');
  
  // 4. Set up a timer to check for data periodically
  setInterval(() => {
    import('./stores/ExchangeDataStore').then((module) => {
      const store = module.ExchangeDataStore.getInstance();
      const currentData = store.getCurrentEquityData();
      
      logger.info('🔍 PERIODIC CHECK - ExchangeDataStore current state:', {
        equityCount: currentData.length,
        hasData: currentData.length > 0,
        symbols: currentData.map((eq: any) => eq.symbol)
      });
    }).catch((error: any) => {
      logger.error('🔍 Error in periodic check:', error.message);
    });
  }, 5000);
}