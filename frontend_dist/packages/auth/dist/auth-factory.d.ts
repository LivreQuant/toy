import { LocalStorageService, SessionStorageService } from '@trading-app/storage';
import { DeviceIdManager } from './device-id-manager';
import { TokenManager } from './token-manager';
import { AuthApiInterface } from './auth-api-interface';
export interface AuthServices {
    deviceIdManager: DeviceIdManager;
    tokenManager: TokenManager;
    localStorageService: LocalStorageService;
    sessionStorageService: SessionStorageService;
}
/**
 * Factory class to create and configure auth services
 */
export declare class AuthFactory {
    /**
     * Creates a complete set of auth services with proper dependencies
     * @param authApi - Optional auth API to set on token manager
     * @returns Configured auth services
     */
    static createAuthServices(authApi?: AuthApiInterface): AuthServices;
    /**
     * Creates just the token manager with dependencies
     * @param authApi - Optional auth API to set
     * @returns Configured token manager
     */
    static createTokenManager(authApi?: AuthApiInterface): TokenManager;
    /**
     * Creates just the device ID manager
     * @returns Configured device ID manager
     */
    static createDeviceIdManager(): DeviceIdManager;
}
