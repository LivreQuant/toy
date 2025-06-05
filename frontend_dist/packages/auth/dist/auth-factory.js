// src/auth-factory.ts
import { LocalStorageService, SessionStorageService } from '@trading-app/storage';
import { DeviceIdManager } from './device-id-manager';
import { TokenManager } from './token-manager';
/**
 * Factory class to create and configure auth services
 */
export class AuthFactory {
    /**
     * Creates a complete set of auth services with proper dependencies
     * @param authApi - Optional auth API to set on token manager
     * @returns Configured auth services
     */
    static createAuthServices(authApi) {
        // Create storage services
        const localStorageService = new LocalStorageService();
        const sessionStorageService = new SessionStorageService();
        // Create device ID manager
        const deviceIdManager = DeviceIdManager.getInstance(sessionStorageService);
        // Create token manager
        const tokenManager = new TokenManager(localStorageService, deviceIdManager);
        // Set auth API if provided
        if (authApi) {
            tokenManager.setAuthApi(authApi);
        }
        return {
            deviceIdManager,
            tokenManager,
            localStorageService,
            sessionStorageService
        };
    }
    /**
     * Creates just the token manager with dependencies
     * @param authApi - Optional auth API to set
     * @returns Configured token manager
     */
    static createTokenManager(authApi) {
        const services = AuthFactory.createAuthServices(authApi);
        return services.tokenManager;
    }
    /**
     * Creates just the device ID manager
     * @returns Configured device ID manager
     */
    static createDeviceIdManager() {
        const sessionStorageService = new SessionStorageService();
        return DeviceIdManager.getInstance(sessionStorageService);
    }
}
