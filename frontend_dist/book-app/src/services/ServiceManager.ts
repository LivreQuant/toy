// frontend_dist/book-app/src/services/ServiceManager.ts
import { getLogger } from '@trading-app/logging';
import { AuthFactory } from '@trading-app/auth';
import { ApiFactory } from '@trading-app/api';
import { ConnectionManager, createConnectionManagerWithGlobalDeps } from '@trading-app/websocket';
import { ConvictionManager } from './convictions/conviction-manager';
import { ExchangeDataHandler } from './ExchangeDataHandler';

const logger = getLogger('ServiceManager');

class ServiceManager {
  private static instance: ServiceManager | null = null;
  private authServices: any = null;
  private apiClients: any = null;
  private connectionManager: ConnectionManager | null = null;
  private convictionManager: ConvictionManager | null = null;
  private exchangeDataHandler: ExchangeDataHandler | null = null;
  private isInitialized = false;

  private constructor() {
    if (process.env.NODE_ENV === 'development') {
      (window as any).serviceManager = this;
      logger.info('🔧 DEV MODE: ServiceManager available as window.serviceManager');
    }
  }

  static getInstance(): ServiceManager {
    if (!ServiceManager.instance) {
      ServiceManager.instance = new ServiceManager();
    }
    return ServiceManager.instance;
  }

  async initialize(bookId: string): Promise<{
    authServices: any;
    apiClients: any;
    connectionManager: ConnectionManager;
    convictionManager: ConvictionManager;
    exchangeDataHandler: ExchangeDataHandler;
  }> {
    // Check if all services are already initialized
    if (this.isInitialized && 
        this.authServices && 
        this.apiClients && 
        this.connectionManager && 
        this.convictionManager && 
        this.exchangeDataHandler) {
      logger.info('🔄 Services already initialized, reusing existing instances');
      return {
        authServices: this.authServices,
        apiClients: this.apiClients,
        connectionManager: this.connectionManager,
        convictionManager: this.convictionManager,
        exchangeDataHandler: this.exchangeDataHandler
      };
    }

    logger.info('🚀 Initializing services for the first time');

    // Create auth services (only once)
    if (!this.authServices) {
      this.authServices = AuthFactory.createAuthServices();
      logger.info('✅ Auth services created');
    }

    // Create API clients (only once)
    if (!this.apiClients) {
      this.apiClients = ApiFactory.createClients(this.authServices.tokenManager);
      this.authServices.tokenManager.setAuthApi(this.apiClients.auth);
      logger.info('✅ API clients created');
    }

    // Create connection manager (only once) - FIXED
    if (!this.connectionManager) {
      // FIXED: Pass the existing TokenManager that already works
      this.connectionManager = createConnectionManagerWithGlobalDeps(this.authServices.tokenManager, bookId);
      logger.info('✅ ConnectionManager created');
    }

    // Create conviction manager (only once)
    if (!this.convictionManager) {
      this.convictionManager = new ConvictionManager(
        this.apiClients.conviction,
        this.authServices.tokenManager
      );
      logger.info('✅ ConvictionManager created');
    }

    // Create exchange data handler (only once)
    if (!this.exchangeDataHandler) {
      this.exchangeDataHandler = new ExchangeDataHandler();
      logger.info('✅ ExchangeDataHandler created and registered');
    }

    this.isInitialized = true;
    logger.info('🎉 All services initialized successfully');

    // FIXED: Add type assertion to ensure non-null values
    return {
      authServices: this.authServices!,
      apiClients: this.apiClients!,
      connectionManager: this.connectionManager!,
      convictionManager: this.convictionManager!,
      exchangeDataHandler: this.exchangeDataHandler!
    };
  }

  getConnectionManager(): ConnectionManager | null {
    return this.connectionManager;
  }

  getExchangeDataHandler(): ExchangeDataHandler | null {
    return this.exchangeDataHandler;
  }

  // Clean up method for testing or logout
  destroy() {
    logger.info('🧹 Destroying service manager');
    if (this.connectionManager) {
      this.connectionManager.disconnect('service_cleanup');
    }
    if (this.exchangeDataHandler) {
      this.exchangeDataHandler.dispose();
    }
    this.authServices = null;
    this.apiClients = null;
    this.connectionManager = null;
    this.convictionManager = null;
    this.exchangeDataHandler = null;
    this.isInitialized = false;
  }

  // Static method to reset for testing
  static reset() {
    if (ServiceManager.instance) {
      ServiceManager.instance.destroy();
      ServiceManager.instance = null;
    }
  }
}

export default ServiceManager;