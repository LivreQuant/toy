// src/services/ServiceManager.ts
import { getLogger } from '@trading-app/logging';
import { AuthFactory } from '@trading-app/auth';
import { ApiFactory } from '@trading-app/api';
import { ConnectionManager, createConnectionManagerWithGlobalDeps } from '@trading-app/websocket';
import { ConvictionManager } from './convictions/conviction-manager';

const logger = getLogger('ServiceManager');

class ServiceManager {
  private static instance: ServiceManager | null = null;
  private authServices: any = null;
  private apiClients: any = null;
  private connectionManager: ConnectionManager | null = null;
  private convictionManager: ConvictionManager | null = null;
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

  async initialize(): Promise<{
    authServices: any;
    apiClients: any;
    connectionManager: ConnectionManager;
    convictionManager: ConvictionManager;
  }> {
    if (this.isInitialized && this.authServices && this.apiClients && this.connectionManager && this.convictionManager) {
      logger.info('🔄 Services already initialized, reusing existing instances');
      return {
        authServices: this.authServices,
        apiClients: this.apiClients,
        connectionManager: this.connectionManager,
        convictionManager: this.convictionManager
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

    // Create connection manager (only once)
    if (!this.connectionManager) {
      const { stateManager, toastService, configService } = createConnectionManagerWithGlobalDeps();
      this.connectionManager = new ConnectionManager(
        this.authServices.tokenManager,
        stateManager,
        toastService,
        configService
      );
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

    this.isInitialized = true;
    logger.info('🎉 All services initialized successfully');

    return {
      authServices: this.authServices,
      apiClients: this.apiClients,
      connectionManager: this.connectionManager,
      convictionManager: this.convictionManager
    };
  }

  // FIXED: Remove the problematic getConnectionState method
  getConnectionManager(): ConnectionManager | null {
    return this.connectionManager;
  }

  // Clean up method for testing or logout
  destroy() {
    logger.info('🧹 Destroying service manager');
    if (this.connectionManager) {
      this.connectionManager.disconnect('service_cleanup');
    }
    this.authServices = null;
    this.apiClients = null;
    this.connectionManager = null;
    this.convictionManager = null;
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